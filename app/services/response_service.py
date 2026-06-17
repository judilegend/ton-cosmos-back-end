from typing import Any, Optional
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

class ServiceResponse:
    """
    Utilitaire standard pour uniformiser les réponses API.
    Utilise jsonable_encoder pour s'assurer que les modèles SQLAlchemy 
    ou Pydantic sont convertibles en JSON.
    """

    @staticmethod
    def success(
        data: Any = None,
        message: str = "Success",
        status_code: int = 200
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder({
                "success": True,
                "status_code": status_code,
                "message": message,
                "data": data
            })
        )

    @staticmethod
    def error(
        message: str = "Error",
        status_code: int = 400,
        data: Optional[Any] = None
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder({
                "success": False,
                "status_code": status_code,
                "message": message,
                "data": data
            })
        )