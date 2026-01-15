import logging
from abc import ABC, abstractmethod

import mailtrap as mt
from django.conf import settings

logger = logging.getLogger(__name__)


class MailServices:
    _providers = {}

    @staticmethod
    def send_verify_mail(verification_url: str, to: str):
        services = MailServices._get_provider('mailtrapsandbox')
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
        services = MailServices._get_provider('mailtrapsandbox')
        message = WelcomeMail.get_message()

        services.send(
            sender_address='services',
            sender_name='hello',
            receiver_address=to,
            category='Welcome Mail',
            **message,
        )

    @classmethod
    def _get_provider(cls, provider: str) -> MailProvider:
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

    @staticmethod
    @abstractmethod
    def _get_body(*args, **kwargs) -> str:
        pass

    @staticmethod
    @abstractmethod
    def _get_html_context(*args, **kwargs) -> str:
        pass


class VerificationMail(MailMessage):
    @staticmethod
    def _get_subject():
        return '[信箱認證] 請認證email帳號'

    @staticmethod
    def _get_body(url: str, **kwargs) -> str:
        if not url:
            raise ValueError('Missing url parameter')

        return f"""
        會員帳號信箱認證

        您好：
        請於 60 分鐘內請點擊認證信箱連結
        {url}
        若非本人操作，請忽略此信。
        """

    @staticmethod
    def _get_html_context(url: str, **kwargs):
        if not url:
            raise ValueError('Missing url parameter')

        text = f"""
        <html>
            <body>
                <h2 style="color: #333;">會員帳號信箱認證</h2>
                <p>您的認證連結如下：</p>
                <div style="background: #f4f4f4; padding: 20px; font-size: 24px;
                font-weight: bold; color: #007bff;">
                <a href="{url}" target="_blank">請點此進行認證</a>
                </div>
                <p>請於 60 分鐘內進行驗證</p>
                <hr>
                <p style="font-size: 12px; color: #888;">若您未曾申請此帳號，請忽略此信。</p>
            </body>
        </html>
        """

        return text


class WelcomeMail(MailMessage):
    @staticmethod
    def _get_subject():
        return '[信箱認證] 認證成功 哇嗚'

    @staticmethod
    def _get_body(**kwargs):
        return """
        您好：
        會員信箱已驗證成功，現在您可以正常使用通知服務。
        """

    @staticmethod
    def _get_html_context(**kwargs) -> str:
        success_text = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
        </head>
        <body style="margin: 0; padding: 0; font-family: 'Microsoft JhengHei', Arial, sans-serif;
        background-color: #ffffff;">
            <div style="max-width: 500px; margin: 40px auto;
            text-align: center; border: 1px solid #e0e0e0;
            border-radius: 10px; padding: 30px;">
                <h2 style="color: #28a745; font-size: 24px; margin-bottom: 20px;">
                    電子信箱認證成功
                </h2>
                <p style="color: #333333; font-size: 16px; line-height: 1.5;">
                    您的帳號已完成驗證，現在您可以正常使用網站服務。
                </p>
                <hr style="border: 0; border-top: 1px solid #f0f0f0; margin: 30px 0;">
                <p style="color: #888888; font-size: 13px;">
                    感謝您的配合。
                </p>
            </div>
        </body>
        </html>
        """

        return success_text


class ResetPasswordMail(MailMessage):
    @staticmethod
    def _get_subject():
        raise NotImplementedError('Not Impl')

    @staticmethod
    def _get_body(**kwargs):
        raise NotImplementedError('Not Impl')


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
        response = client.send(mail)
        logger.info(f'[MailTrapSandbox] Send response: {response}')


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
        response = client.send(mail)
        logger.info(f'[MailTrap] Send response: {response}')
