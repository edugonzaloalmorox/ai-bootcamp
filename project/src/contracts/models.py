from datetime import datetime
import re
from typing import Dict, Optional

from pydantic import BaseModel, Field, validator
import dateparser 


# -------------------- Parsers auxiliares --------------------


def parse_amount(value: Optional[str]) -> Optional[float]:
    """
    Convierte cadenas como '235.122,56 euros' a float 235122.56.
    Asume formato español (punto miles, coma decimal).
    """
    if not value:
        return None

    clean = value.lower().replace("euros", "")
    # eliminar espacios
    clean = clean.replace(" ", "")
    # eliminar separador de miles '.'
    clean = clean.replace(".", "")
    # convertir coma decimal a punto
    clean = clean.replace(",", ".")

    try:
        return float(clean)
    except ValueError:
        return None


def parse_duration_months(value: Optional[str]) -> Optional[int]:
    """
    Convierte '2 meses' → 2.
    Si no encuentra número devuelve None.
    """
    if not value:
        return None
    m = re.search(r"(\d+)", value)
    return int(m.group(1)) if m else None


def parse_deadline(value: Optional[str]) -> Optional[datetime]:
    """
    Convierte '27 de octubre del 2025 18:00' → datetime.
    Usa dateparser con configuración básica en español.
    """
    if not value:
        return None

    dt = dateparser.parse(value, languages=["es"])
    return dt


# -------------------- Metadatos brutos --------------------


class ContractMetadataRaw(BaseModel):
    """
    Metadatos tal y como se extraen del HTML.
    El scraper puede devolver claves arbitrarias, así que aquí permitimos campos dinámicos.
    Esto mantiene trazabilidad total.
    """

    data: Dict[str, Optional[str]] = Field(
        ..., description="Metadatos en bruto extraídos del HTML."
    )

    def get(self, key: str) -> Optional[str]:
        return self.data.get(key)


class ContractMetadataCanonical(BaseModel):
    """
    Versión limpia y tipada de los metadatos del contrato.
    Construida a partir de ContractMetadataRaw.
    """

    contract_id: Optional[str] = None
    reference: Optional[str] = None
    object_description: Optional[str] = None
    contract_type: Optional[str] = None
    cpv_code: Optional[str] = None
    harmonized: Optional[bool] = None
    nuts_code: Optional[str] = None
    estimated_value_eur: Optional[float] = None
    budget_base_eur: Optional[float] = None
    budget_total_eur: Optional[float] = None
    duration_months: Optional[int] = None
    deadline: Optional[datetime] = None

    @classmethod
    def from_raw(cls, raw: ContractMetadataRaw) -> "ContractMetadataCanonical":
        d = raw.data

        harmonized_raw = (d.get("Sujeto a regulación armonizada") or "").strip().lower()
        harmonized_bool = harmonized_raw in {"sí", "si", "yes", "y"}

        return cls(
            contract_id=d.get("Número de expediente"),
            reference=d.get("Referencia"),
            object_description=d.get("Objeto del contrato"),
            contract_type=d.get("Tipo de contrato"),
            cpv_code=d.get("Código CPV"),
            harmonized=harmonized_bool,
            nuts_code=d.get("Código NUTS"),
            estimated_value_eur=parse_amount(d.get("Valor estimado sin impuestos")),
            budget_base_eur=parse_amount(d.get("Presupuesto base licitación sin impuestos")),
            budget_total_eur=parse_amount(d.get("Presupuesto base licitación. Importe total")),
            duration_months=parse_duration_months(d.get("Duración del contrato")),
            deadline=parse_deadline(
                d.get(
                    "Fecha y hora límite de presentación de ofertas o solicitudes de participación"
                )
            ),
        )




class ContractRecord(BaseModel):
    """
    Representa lo que sabemos de un contrato justo después del scraping.

    - contract_id: identificador estable del contrato
    - detail_url: URL de la página de detalle
    - metadata_raw: metadatos extraídos del HTML tal cual
    - metadata: metadatos canónicos/normalizados
    - pdfs: mapeo {tipo_pliego: ruta_local_pdf}

    Este modelo valida datos y permite futuros campos (texto, embeddings, perfil).
    """

    contract_id: str = Field(
        ..., description="Identificador del contrato (expediente)"
    )
    detail_url: str = Field(
        ..., description="URL de detalle en el portal público"
    )
    metadata_raw: ContractMetadataRaw = Field(
        ..., description="Metadatos brutos del HTML"
    )
    metadata: ContractMetadataCanonical = Field(
        ..., description="Metadatos normalizados y tipados"
    )
    pdfs: Dict[str, str] = Field(
        default_factory=dict,
        description="Rutas locales a PDFs descargados",
    )

    @validator("contract_id")
    def normalize_contract_id(cls, v: str) -> str:
        # Limpieza básica para evitar IDs raros
        if not v or not isinstance(v, str):
            return "unknown"
        v = v.strip()
        return v or "unknown"
