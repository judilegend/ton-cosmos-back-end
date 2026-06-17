import os
import asyncio
from concurrent.futures import ProcessPoolExecutor
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from datetime import datetime, timezone
from typing import Dict, Any
import logging


logger = logging.getLogger(__name__)
pdf_executor = ProcessPoolExecutor(max_workers=2)

BASE_DIR = "/app/static/reports"

def _render_pdf_task(html_content, pdf_path):
    HTML(string=html_content, base_url="/app").write_pdf(pdf_path)

class PDFService:
    def __init__(self):
        template_path = os.path.join(os.path.dirname(__file__), "../templates")
        self.env = Environment(loader=FileSystemLoader(template_path))


    async def render_template(self, template_name: str, data: Dict[str, Any]) -> str:
        try:
            template = self.env.get_template(f"reports_pdf/{template_name}.html")
            now = datetime.now(timezone.utc).strftime("%d/%m/%Y")
            return template.render(**data, generated_at=now)

        except TemplateNotFound:
            raise Exception(f"Report template '{template_name}' not found")
        except Exception as e:
            raise Exception(f"Template rendering error: {str(e)}")
        
        
    async def generate_astrological_report(self, template_name: str, data: Dict[str, Any], output_filename: str) -> str:
        os.makedirs(BASE_DIR, exist_ok=True)
        pdf_path = os.path.join(BASE_DIR, output_filename)

        html_content = await self.render_template(template_name, data)

        loop = asyncio.get_running_loop()
        
        try:
            await asyncio.wait_for(
                loop.run_in_executor(
                    pdf_executor,
                    _render_pdf_task,
                    html_content,
                    pdf_path
                ),
                timeout=150.0
            )

            return f"/reports/{output_filename}"
        
        except asyncio.TimeoutError:
            logger.error("Timeout lors du rendu PDF")
            raise Exception("Le rendu du document a pris trop de temps.")
        