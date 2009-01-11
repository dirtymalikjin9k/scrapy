"""
Mail sending helpers

See documentation in docs/ref/email.rst
"""
from cStringIO import StringIO
from email.MIMEMultipart import MIMEMultipart
from email.MIMENonMultipart import MIMENonMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders

from twisted.internet import defer, reactor
from twisted.mail.smtp import SMTPSenderFactory

from scrapy import log
from scrapy.core.exceptions import NotConfigured
from scrapy.conf import settings

class MailSender(object):

    def __init__(self, smtphost=None, mailfrom=None):
        self.smtphost = smtphost if smtphost else settings['MAIL_HOST']
        self.mailfrom = mailfrom if mailfrom else settings['MAIL_FROM']

        if not self.smtphost or not self.mailfrom:
            raise NotConfigured("MAIL_HOST and MAIL_FROM settings are required")

    def send(self, to, subject, body, cc=None, attachs=()):
        if attachs:
            msg = MIMEMultipart()
        else:
            msg = MIMENonMultipart('text', 'plain')
        msg['From'] = self.mailfrom
        msg['To'] = COMMASPACE.join(to)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject
        rcpts = to[:]
        if cc:
            rcpts.extend(cc)
            msg['Cc'] = COMMASPACE.join(cc)

        if attachs:
            msg.attach(MIMEText(body))
            for attach_name, mimetype, f in attachs:
                part = MIMEBase(*mimetype.split('/'))
                part.set_payload(f.read())
                Encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment; filename="%s"' % attach_name)
                msg.attach(part)
        else:
            msg.set_payload(body)

        dfd = self._sendmail(self.smtphost, self.mailfrom, rcpts, msg.as_string())
        dfd.addCallbacks(self._sent_ok, self._sent_failed,
            callbackArgs=[to, cc, subject, len(attachs)],
            errbackArgs=[to, cc, subject, len(attachs)])

    def _sent_ok(self, result, to, cc, subject, nattachs):
        log.msg('Mail sent OK: To=%s Cc=%s Subject="%s" Attachs=%d' % (to, cc, subject, nattachs))

    def _sent_failed(self, failure, to, cc, subject, nattachs):
        errstr = str(failure.value)
        log.msg('Unable to send mail: To=%s Cc=%s Subject="%s" Attachs=%d - %s' % (to, cc, subject, nattachs, errstr), level=log.ERROR)

    def _sendmail(self, smtphost, from_addr, to_addrs, msg, port=25):
        """ This is based on twisted.mail.smtp.sendmail except that it
        instantiates a quiet (noisy=False) SMTPSenderFactory """
        msg = StringIO(msg)
        d = defer.Deferred()
        factory = SMTPSenderFactory(from_addr, to_addrs, msg, d)
        factory.noisy = False
        reactor.connectTCP(smtphost, port, factory)
        return d

