import logging
from abc import ABC, abstractmethod

import mailtrap as mt
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class MailServices:
    _providers = {}

    @staticmethod
    def send_verify_mail(verification_url: str, to: str):
        services = MailServices._get_provider()
        message = VerificationMail.get_message(url=verification_url)

        services.send(
            sender_address='services',
            sender_name='hello',
            receiver_address=to,
            category='Verification Mail',
            **message,
        )

    @staticmethod
    def send_welcome_mail(to: str):
        services = MailServices._get_provider()
        message = WelcomeMail.get_message()

        services.send(
            sender_address='services',
            sender_name='hello',
            receiver_address=to,
            category='Welcome Mail',
            **message,
        )

    @staticmethod
    def send_reset_password_mail(code: str, to: str):
        services = MailServices._get_provider()
        message = ResetPasswordMail.get_message(code=code)

        services.send(
            sender_address='services',
            sender_name='hello',
            receiver_address=to,
            category='Rest password Mail',
            **message,
        )

    @classmethod
    def _get_provider(cls, provider: str = 'mailtrapsandbox') -> MailProvider:
        if settings.DEBUG is not True:
            provider = 'mailtrap'
        target_class = cls._providers.get(provider)
        if not target_class:
            raise ValueError(f'unsupported mail provider: {provider}')
        return target_class()

    @classmethod
    def register(cls, name):
        def warpper(warpper_class):
            cls._providers[name.lower()] = warpper_class
            return warpper_class

        return warpper


class MailMessage(ABC):
    @classmethod
    def get_message(cls, **kwargs):
        return {
            'subject': cls._get_subject(),
            'text': cls._get_body(**kwargs),
            'html': cls._get_html_context(**kwargs),
        }

    @staticmethod
    @abstractmethod
    def _get_subject() -> str:
        pass

    @classmethod
    def _get_body(cls, **kwargs) -> str:
        return render_to_string(f'{cls.template_name}.txt', kwargs)

    @classmethod
    def _get_html_context(cls, **kwargs) -> str:
        return render_to_string(f'{cls.template_name}.html', kwargs)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, 'template_name', None):
            raise TypeError(f'Class {cls.__name__} must define "template_name"')


class VerificationMail(MailMessage):
    template_name = 'emails/verification_email'

    @staticmethod
    def _get_subject():
        return '[信箱認證] 請認證email帳號'

    @classmethod
    def _get_body(cls, url: str, **kwargs) -> str:
        if not url:
            raise ValueError('Missing url parameter')
        return super()._get_body(url=url, **kwargs)

    @classmethod
    def _get_html_context(cls, url: str, **kwargs):
        if not url:
            raise ValueError('Missing url parameter')
        return super()._get_html_context(url=url, **kwargs)


class WelcomeMail(MailMessage):
    template_name = 'emails/welcome_email'

    @staticmethod
    def _get_subject():
        return '[信箱認證] 認證成功 哇嗚'


class ResetPasswordMail(MailMessage):
    template_name = 'emails/reset_password_email'

    @staticmethod
    def _get_subject():
        return '[密碼重設] 請接收重設驗證碼'


class MailProvider(ABC):
    @classmethod
    @abstractmethod
    def send(cls, *, sender_address, sender_name, receiver_address, subject, text, html, category):
        pass


@MailServices.register('mailtrapsandbox')
class MailTrapSandboxProvider(MailProvider):
    @classmethod
    def send(cls, *, sender_address, sender_name, receiver_address, subject, text, html, category):
        mailtrap_key = settings.MAILTRAP_API_KEY
        is_sandbox = settings.MAILTRAP_USE_SANDBOX
        inbox_id = settings.MAILTRAP_INBOX_ID

        master_domain = settings.MAILTRAP_DOMAIN
        master_email = f'{sender_address}@{master_domain}'
        master_name = sender_name
        slave_email = receiver_address
        slave_subject = subject
        slave_text = text
        slave_html = html
        slave_category = category

        client_kwargs = {'token': mailtrap_key}
        if is_sandbox and inbox_id:
            client_kwargs['sandbox'] = True
            client_kwargs['inbox_id'] = inbox_id

        client = mt.MailtrapClient(**client_kwargs)

        mail = mt.Mail(
            sender=mt.Address(email=master_email, name=master_name),
            to=[mt.Address(email=slave_email)],
            subject=slave_subject,
            text=slave_text,
            html=slave_html,
            category=slave_category,
        )
        try:
            response = client.send(mail)
            logger.info(f'[MailTrapSandbox] Send response: {response}')
        except mt.MailtrapError as e:
            logger.error(f'[MailTrapSandbox] MailtrapError: {e}')


@MailServices.register('mailtrap')
class MailTrapProvider(MailProvider):
    @classmethod
    def send(cls, *, sender_address, sender_name, receiver_address, subject, text, html, category):
        mailtrap_key = settings.MAILTRAP_API_KEY

        master_domain = settings.MAILTRAP_DOMAIN
        master_email = f'{sender_address}@{master_domain}'
        master_name = sender_name
        slave_email = receiver_address
        slave_subject = subject
        slave_text = text
        slave_html = html
        slave_category = category

        client = mt.MailtrapClient(token=mailtrap_key)

        mail = mt.Mail(
            sender=mt.Address(email=master_email, name=master_name),
            to=[mt.Address(email=slave_email)],
            subject=slave_subject,
            text=slave_text,
            html=slave_html,
            category=slave_category,
        )
        try:
            response = client.send(mail)
            logger.info(f'[MailTrap] Send response: {response}')
        except mt.MailtrapError as e:
            logger.error(f'[MailTrap] MailtrapError: {e}')
