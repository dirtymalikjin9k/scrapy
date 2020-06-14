import logging

from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import (
    ConnectionTerminated, DataReceived, ResponseReceived,
    StreamEnded, StreamReset, WindowUpdated
)
from twisted.internet.protocol import connectionDone, Protocol

from scrapy.core.http2.stream import Stream
from scrapy.http import Request

LOGGER = logging.getLogger(__name__)


class H2ClientProtocol(Protocol):
    # TODO:
    #  1. Check for user-agent while testing
    #  2. Add support for cookies
    #  3. Handle priority updates (Not required)
    #  4. Handle case when received events have StreamID = 0 (applied to H2Connection)
    #  1 & 2:
    #   - Automatically handled by the Request middleware
    #   - request.headers will have 'Set-Cookie' value

    def __init__(self):
        config = H2Configuration(client_side=True, header_encoding='utf-8')
        self.conn = H2Connection(config=config)

        # Address of the server we are connected to
        # these are updated when connection is successfully made
        self.destination = None

        # ID of the next request stream
        # Following the convention made by hyper-h2 each client ID
        # will be odd.
        self.next_stream_id = 1

        # Streams are stored in a dictionary keyed off their stream IDs
        self.streams = {}

        # Boolean to keep track the connection is made
        # If requests are received before connection is made
        # we keep all requests in a pool and send them as the connection
        # is made
        self.is_connection_made = False
        self._pending_request_stream_pool = []

    def _stream_close_cb(self, stream_id: int):
        """Called when stream is closed completely
        """
        try:
            del self.streams[stream_id]
        except KeyError:
            pass

    def _new_stream(self, request: Request):
        """Instantiates a new Stream object
        """
        stream_id = self.next_stream_id
        self.next_stream_id += 2

        stream = Stream(
            stream_id=stream_id,
            request=request,
            connection=self.conn,
            write_to_transport=self._write_to_transport,
            cb_close=lambda: self._stream_close_cb(stream_id)
        )

        self.streams[stream.stream_id] = stream
        return stream

    def _send_pending_requests(self):
        # TODO: handle MAX_CONCURRENT_STREAMS
        # Initiate all pending requests
        for stream in self._pending_request_stream_pool:
            stream.initiate_request()

        self._pending_request_stream_pool.clear()

    def _write_to_transport(self):
        """ Write data to the underlying transport connection
        from the HTTP2 connection instance if any
        """
        data = self.conn.data_to_send()
        self.transport.write(data)

    def request(self, _request: Request):
        stream = self._new_stream(_request)
        d = stream.get_response()

        # If connection is not yet established then add the
        # stream to pool or initiate request
        if self.is_connection_made:
            stream.initiate_request()
        else:
            self._pending_request_stream_pool.append(stream)

        return d

    def connectionMade(self):
        """Called by Twisted when the connection is established. We can start
        sending some data now: we should open with the connection preamble.
        """
        self.destination = self.transport.connector.getDestination()
        LOGGER.info('Connection made to {}'.format(self.destination))

        self.conn.initiate_connection()
        self._write_to_transport()
        self.is_connection_made = True

        self._send_pending_requests()

    def dataReceived(self, data):
        events = self.conn.receive_data(data)
        self._handle_events(events)
        self._write_to_transport()

    def connectionLost(self, reason=connectionDone):
        """Called by Twisted when the transport connection is lost.
        No need to write anything to transport here.
        """
        # Pop all streams which were pending and were not yet started
        for stream_id in list(self.streams):
            try:
                self.streams[stream_id].lost_connection()
            except KeyError:
                pass

        self.conn.close_connection()

        LOGGER.info("Connection lost with reason " + str(reason))

    def _handle_events(self, events):
        """Private method which acts as a bridge between the events
        received from the HTTP/2 data and IH2EventsHandler

        Arguments:
            events {list} -- A list of events that the remote peer
                triggered by sending data
        """
        for event in events:
            LOGGER.debug(event)
            if isinstance(event, ConnectionTerminated):
                self.connection_terminated(event)
            elif isinstance(event, DataReceived):
                self.data_received(event)
            elif isinstance(event, ResponseReceived):
                self.response_received(event)
            elif isinstance(event, StreamEnded):
                self.stream_ended(event)
            elif isinstance(event, StreamReset):
                self.stream_reset(event)
            elif isinstance(event, WindowUpdated):
                self.window_updated(event)
            else:
                LOGGER.info("Received unhandled event {}".format(event))

    # Event handler functions starts here
    def connection_terminated(self, event: ConnectionTerminated):
        pass

    def data_received(self, event: DataReceived):
        stream_id = event.stream_id
        self.streams[stream_id].receive_data(event.data, event.flow_controlled_length)

    def response_received(self, event: ResponseReceived):
        stream_id = event.stream_id
        self.streams[stream_id].receive_headers(event.headers)

    def stream_ended(self, event: StreamEnded):
        stream_id = event.stream_id
        self.streams[stream_id].end_stream()

    def stream_reset(self, event: StreamReset):
        # TODO: event.stream_id was abruptly closed
        #  Q. What should be the response? (Failure/Partial/???)
        self.streams[event.stream_id].reset()

    def window_updated(self, event: WindowUpdated):
        stream_id = event.stream_id
        if stream_id != 0:
            self.streams[stream_id].receive_window_update(event.delta)
        else:
            # TODO:
            #  Q. What to do when StreamID=0 ?
            pass
