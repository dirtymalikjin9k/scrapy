"""
Limits the scheduler request queue from the point of view of the spider.
That is, if the scheduler queue contains an equal or greater ammount of
requests than the specified limit, the further requests generated by the
spider will be ignored.
The limit is setted from the spider attribute "requests_queue_size". If not
found, from the scrapy setting "REQUESTS_QUEUE_SIZE". If not found, no limit
will be applied. If given a value of 0, no limit will be applied.
"""
from scrapy.core.engine import scrapyengine
from scrapy.conf import settings
from scrapy.http import Request
from scrapy.core import log

class RequestLimitMiddleware(object):
    #_last_queue_size = 0
    def process_result(self, response, result, spider):
        requests = []
        other = []
        [requests.append(r) if isinstance(r, Request) else other.append(r) for r in result]

        max_pending = spider.requests_queue_size if hasattr(spider,"requests_queue_size") else settings.getint("REQUESTS_QUEUE_SIZE")
        if not max_pending:
            accepted = requests
        else:
            free_slots = max_pending - len(scrapyengine.scheduler.pending_requests[spider.domain_name])
            accepted = requests[:free_slots]
            dropped = set(requests) - set(accepted)
            if dropped:
                for r in dropped:
                    log.msg("Ignoring link (max schedule queue size reached): %s " % r.url, level=log.WARNING, domain=spider.domain_name)
        #actual_size = len(scrapyengine.scheduler.pending_requests[spider.domain_name])
        #log.msg("queue size: %d (%+d)" % (actual_size, actual_size - self._last_queue_size) )
        #self._last_queue_size = actual_size
        return accepted + other
