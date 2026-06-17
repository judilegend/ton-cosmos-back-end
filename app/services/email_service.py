import os
import resend
import asyncio
import base64
import aiosmtplib
from email.message import EmailMessage
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
from app.core.config import settings
from typing import Dict, Any, Optional


class EmailService:
    def __init__(self):
        template_path = os.path.join(os.path.dirname('%s' % __file__), "../templates")
        self.env = Environment(
            loader=FileSystemLoader(template_path),
            autoescape=select_autoescape(["html", "xml"])
        )
        
        resend.api_key = settings.RESEND_API_KEY

    def _render_template(self, template_name: str, data: Dict[str, Any]) -> str:
        try:
            template = self.env.get_template(f"emails/{template_name}.html")
            return template.render(**data)
        except TemplateNotFound:
            raise Exception(f"Email template '{template_name}' not found")
        except Exception as e:
            raise Exception(f"Template rendering error: {str(e)}")


    async def _wait_for_file(self, path: str, timeout: int = 5) -> bool:
        for _ in range(timeout * 2):
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return True
            await asyncio.sleep(0.5)
        return False
    
    
    async def _send_via_resend(self, to: str, subject: str, html_content: str, attachment_path: Optional[str]) -> bool:
        params = {
            "from": settings.RESEND_API_FROM,
            "to": [to],
            "subject": subject,
            "html": html_content,
        }

        if attachment_path:
            if await self._wait_for_file(attachment_path):
                with open(attachment_path, "rb") as f:
                    file_data = f.read()
                file_name = os.path.basename(attachment_path)
                base64_content = base64.b64encode(file_data).decode("utf-8")
                params["attachments"] = [{"filename": file_name, "content": base64_content}]
            else:
                print(f"[ERROR] La pièce jointe est introuvable ou vide après attente : {attachment_path}")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: resend.Emails.send(params))
        return True


    async def _send_via_smtp(self, to: str, subject: str, html_content: str, attachment_path: Optional[str]):
        message = EmailMessage()
        message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
        message["To"] = to
        message["Subject"] = subject
        message.set_content("Veuillez consulter cet email dans un client supportant le HTML.")
        message.add_alternative(html_content, subtype="html")

        if attachment_path:
            if await self._wait_for_file(attachment_path):
                with open(attachment_path, "rb") as f:
                    file_data = f.read()
                file_name = os.path.basename(attachment_path)
                message.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="pdf",
                    filename=file_name
                )
            else:
                print(f"[ERROR] La pièce jointe est introuvable ou vide après attente : {attachment_path}")

        await aiosmtplib.send(
            message,
            hostname=settings.MAIL_HOST,
            port=settings.MAIL_PORT,
            username=settings.MAIL_USERNAME,
            password=settings.MAIL_PASSWORD,
            start_tls=settings.MAIL_STARTTLS,
            use_tls=settings.MAIL_SSL,
        )


    async def send_email(
        self, 
        to: str, 
        subject: str, 
        template_name: str, 
        data: Dict[str, Any], 
        attachment_path: Optional[str] = None,
        use_resend: bool = False
    ) -> Dict[str, Any]:
        try:
            html_content = self._render_template(template_name, data)
        except Exception as e:
            return {"success": False, "message": f"Erreur template: {str(e)}"}

        if settings.RESEND_API_KEY and use_resend:
            try:
                await self._send_via_resend(to, subject, html_content, attachment_path)
                return {"success": True, "message": "Email envoyé avec succès via Resend (API)"}
            except Exception as resend_err:
                print(f"[WARNING] Échec Resend, bascule sur SMTP: {resend_err}")

        try:
            await self._send_via_smtp(to, subject, html_content, attachment_path)
            return {"success": True, "message": "Email envoyé avec succès via Gmail (SMTP)"}
        except aiosmtplib.SMTPException as smtp_err:
            print(f"SMTP Error: {smtp_err}")
            return {"success": False, "message": f"Erreur de secours SMTP: {str(smtp_err)}"}
        except Exception as e:
            print(f"Unexpected Email Error: {e}")
            return {"success": False, "message": f"Erreur inattendue: {str(e)}"}
        