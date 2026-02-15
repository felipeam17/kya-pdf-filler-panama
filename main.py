# main.py
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PyPDFForm import PdfWrapper
import tempfile
import os
from typing import Optional, Dict
import requests
from datetime import datetime

app = FastAPI(title="KYC PDF Filler Panama")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= MODELOS =============
class ClienteKYC(BaseModel):
    nombre_completo: str
    cedula: str
    pasaporte: Optional[str] = ""
    fecha_nacimiento: str
    nacionalidad: str
    estado_civil: str
    direccion_completa: str
    provincia: str
    distrito: str
    corregimiento: str
    telefono: str
    email: str
    ocupacion: str
    empresa: str
    cargo: str
    ingresos_mensuales: float
    origen_fondos: str
    nit: Optional[str] = ""
    ruc: Optional[str] = ""
    es_pep: bool = False

class FormularioRequest(BaseModel):
    institucion: str
    cliente: ClienteKYC
    template_url: Optional[str] = None

# ============= MAPEOS PARA TUS FORMULARIOS REALES =============

MAPEOS_INSTITUCIONES = {
    # MORGAN & MORGAN - PERSONA NATURAL
    "morgan_morgan_natural": {
        "nombre_completo": lambda c: c.nombre_completo,
        "nacionalidad_origen": lambda c: c.nacionalidad,
        "otras_nacionalidades": lambda c: "",  # Dejar vacío por ahora
        "telefono": lambda c: c.telefono,
        "email": lambda c: c.email,
        "direccion_fisica": lambda c: c.direccion_completa,
        "ocupacion_actividad": lambda c: c.ocupacion,
        "pais_ocupacion": lambda c: "Panamá",  # Por defecto
        "requiere_licencia": lambda c: "NO",  # Checkbox
        "numero_ruc": lambda c: c.ruc if c.ruc else "",
        "dv": lambda c: "",  # Dígito verificador
        "numero_tributario": lambda c: c.nit if c.nit else "",
        "pais_residencia_fiscal": lambda c: "Panamá",  # Por defecto
        "origen_riqueza_salarios": lambda c: "X" if "salario" in c.origen_fondos.lower() else "",
        "origen_riqueza_pensiones": lambda c: "X" if "pension" in c.origen_fondos.lower() else "",
        "origen_riqueza_renta": lambda c: "X" if "alquiler" in c.origen_fondos.lower() or "renta" in c.origen_fondos.lower() else "",
        "origen_riqueza_dividendos": lambda c: "X" if "dividendo" in c.origen_fondos.lower() else "",
        "origen_riqueza_herencia": lambda c: "X" if "herencia" in c.origen_fondos.lower() else "",
        "origen_riqueza_otro": lambda c: "X" if c.origen_fondos and c.origen_fondos.lower() not in ["salario", "pension", "alquiler", "renta", "dividendo", "herencia"] else "",
        "pais_origen_riqueza": lambda c: "Panamá",  # Por defecto
        "referencia_banco_nombre": lambda c: "",  # Referencias dejadas vacías
        "referencia_banco_contacto": lambda c: "",
        "referencia_banco_telefono": lambda c: "",
        "referencia_banco_email": lambda c: "",
        "nombre_declarante": lambda c: c.nombre_completo,
        "cedula_declarante": lambda c: c.cedula,
        "fecha_declaracion": lambda c: datetime.now().strftime("%d/%m/%Y"),
    },
    
    # MORGAN & MORGAN - PERSONA JURÍDICA
    "morgan_morgan_juridica": {
        "nombre_completo_empresa": lambda c: c.empresa if c.empresa else c.nombre_completo,
        "telefono": lambda c: c.telefono,
        "email": lambda c: c.email,
        "actividad": lambda c: c.ocupacion,
        "pais_actividad": lambda c: "Panamá",
        "direccion_actividad": lambda c: c.direccion_completa,
        "requiere_licencia": lambda c: "NO",
        "numero_ruc": lambda c: c.ruc if c.ruc else "",
        "dv": lambda c: "",
        "numero_tributario": lambda c: c.nit if c.nit else "",
        "pais_residencia_fiscal": lambda c: "Panamá",
        "origen_fondos_salarios": lambda c: "X" if "salario" in c.origen_fondos.lower() else "",
        "origen_fondos_pensiones": lambda c: "X" if "pension" in c.origen_fondos.lower() else "",
        "origen_fondos_venta_acciones": lambda c: "X" if "acciones" in c.origen_fondos.lower() else "",
        "origen_fondos_renta": lambda c: "X" if "alquiler" in c.origen_fondos.lower() or "renta" in c.origen_fondos.lower() else "",
        "origen_fondos_dividendos": lambda c: "X" if "dividendo" in c.origen_fondos.lower() else "",
        "origen_fondos_otro": lambda c: c.origen_fondos if c.origen_fondos.lower() not in ["salario", "pension", "acciones", "alquiler", "renta", "dividendo"] else "",
        "pais_origen_fondos": lambda c: "Panamá",
        "referencia_banco_nombre": lambda c: "",
        "referencia_banco_contacto": lambda c: "",
        "referencia_banco_telefono": lambda c: "",
        "referencia_banco_email": lambda c: "",
        "nombre_declarante": lambda c: c.nombre_completo,
        "cedula_declarante": lambda c: c.cedula,
        "fecha_declaracion": lambda c: datetime.now().strftime("%d/%m/%Y"),
    },
    
    # MMG BANK - PERSONA NATURAL
    "mmg_bank": {
        "primer_nombre": lambda c: c.nombre_completo.split()[0] if c.nombre_completo else "",
        "segundo_nombre": lambda c: c.nombre_completo.split()[1] if len(c.nombre_completo.split()) > 2 else "",
        "primer_apellido": lambda c: c.nombre_completo.split()[-2] if len(c.nombre_completo.split()) > 1 else "",
        "segundo_apellido": lambda c: c.nombre_completo.split()[-1] if len(c.nombre_completo.split()) > 2 else "",
        "genero_f": lambda c: "X" if c.nombre_completo and any(name in c.nombre_completo.lower() for name in ["maria", "ana", "carmen"]) else "",
        "genero_m": lambda c: "X" if c.nombre_completo and not any(name in c.nombre_completo.lower() for name in ["maria", "ana", "carmen"]) else "",
        "cedula": lambda c: "X",  # Checkbox que usa cédula
        "pasaporte": lambda c: "",  # Checkbox que usa pasaporte
        "numero_identificacion": lambda c: c.cedula,
        "fecha_expiracion": lambda c: "",  # No tenemos este dato
        "fecha_nacimiento": lambda c: c.fecha_nacimiento,
        "pais_nacimiento": lambda c: "Panamá",
        "nacionalidad": lambda c: c.nacionalidad,
        "residencia_fiscal": lambda c: "Panamá",
        "numero_contribuyente": lambda c: c.nit if c.nit else c.ruc if c.ruc else "",
        "direccion_residencial": lambda c: c.direccion_completa,
        "corregimiento": lambda c: c.corregimiento,
        "provincia": lambda c: c.provincia,
        "pais": lambda c: "Panamá",
        "correo": lambda c: c.email,
        "telefono": lambda c: c.telefono,
        "celular": lambda c: c.telefono,
        "estado_civil_soltero": lambda c: "X" if c.estado_civil and "soltero" in c.estado_civil.lower() else "",
        "estado_civil_casado": lambda c: "X" if c.estado_civil and "casado" in c.estado_civil.lower() else "",
        "nombre_conyuge": lambda c: "",  # No lo tenemos
        "dependientes": lambda c: "0",  # Por defecto
        "sector_publico": lambda c: "",
        "sector_privado": lambda c: "X",  # Por defecto
        "empleado_domestico": lambda c: "",
        "cuenta_propia": lambda c: "X" if c.empresa and "independiente" in c.empresa.lower() else "",
        "patrono": lambda c: "",
        "trabajador_familiar": lambda c: "",
        "cooperativa": lambda c: "",
        "jubilado": lambda c: "",
        "desempleado": lambda c: "",
        "nivel_primaria": lambda c: "",
        "nivel_secundaria": lambda c: "",
        "nivel_tecnico": lambda c: "",
        "nivel_universitario_lic": lambda c: "X",  # Por defecto
        "nivel_universitario_maestria": lambda c: "",
        "profesion": lambda c: c.ocupacion,
        "cargo": lambda c: c.cargo,
        "empresa": lambda c: c.empresa,
        "tipo_negocio": lambda c: "",
        "telefono_empresa": lambda c: c.telefono,
        "celular_empresa": lambda c: c.telefono,
        "correo_empresa": lambda c: c.email,
        "direccion_laboral": lambda c: c.direccion_completa,
        "pais_laboral": lambda c: "Panamá",
        "salario_bruto": lambda c: f"${c.ingresos_mensuales:,.2f}",
        "ingreso_neto": lambda c: f"${c.ingresos_mensuales * 0.85:,.2f}",  # Aproximado
        "otros_ingresos": lambda c: "$0.00",
        "fecha_ingreso": lambda c: "",
        "ingreso_anual_menos_50k": lambda c: "X" if c.ingresos_mensuales * 12 < 50000 else "",
        "ingreso_anual_50k_150k": lambda c: "X" if 50000 <= c.ingresos_mensuales * 12 <= 150000 else "",
        "ingreso_anual_150k_250k": lambda c: "X" if 150000 < c.ingresos_mensuales * 12 <= 250000 else "",
        "ingreso_anual_250k_500k": lambda c: "X" if 250000 < c.ingresos_mensuales * 12 <= 500000 else "",
        "ingreso_anual_mas_500k": lambda c: "X" if c.ingresos_mensuales * 12 > 500000 else "",
        "otras_nacionalidades_si": lambda c: "",
        "otras_nacionalidades_no": lambda c: "X",
        "renunciado_nacionalidad_si": lambda c: "",
        "renunciado_nacionalidad_no": lambda c: "X",
        "intermediario_si": lambda c: "",
        "intermediario_no": lambda c: "X",
        "pep_si": lambda c: "X" if c.es_pep else "",
        "pep_no": lambda c: "X" if not c.es_pep else "",
        "referencia_banco_1": lambda c: "",
        "referencia_banco_1_contacto": lambda c: "",
        "referencia_banco_1_telefono": lambda c: "",
        "referencia_banco_1_email": lambda c: "",
        "referencia_banco_2": lambda c: "",
        "referencia_banco_2_contacto": lambda c: "",
        "referencia_banco_2_telefono": lambda c: "",
        "referencia_banco_2_email": lambda c: "",
        "nombre_firma": lambda c: c.nombre_completo,
        "fecha_firma": lambda c: datetime.now().strftime("%d/%m/%Y"),
    },
    
    # SEGUROS GENÉRICO - PERSONA NATURAL
    "seguros_generico": {
        "apellido_1": lambda c: c.nombre_completo.split()[-2] if len(c.nombre_completo.split()) > 1 else "",
        "apellido_2": lambda c: c.nombre_completo.split()[-1] if len(c.nombre_completo.split()) > 2 else "",
        "nombre_1": lambda c: c.nombre_completo.split()[0] if c.nombre_completo else "",
        "nombre_2": lambda c: c.nombre_completo.split()[1] if len(c.nombre_completo.split()) > 2 else "",
        "fecha_nacimiento": lambda c: c.fecha_nacimiento,
        "pais_nacimiento": lambda c: "Panamá",
        "nacionalidad": lambda c: c.nacionalidad,
        "pais_residencia": lambda c: "Panamá",
        "cedula": lambda c: c.cedula,
        "pasaporte": lambda c: c.pasaporte if c.pasaporte else "",
        "estado_civil": lambda c: c.estado_civil,
        "direccion_residencial": lambda c: c.direccion_completa,
        "pais_direccion": lambda c: "Panamá",
        "correo": lambda c: c.email,
        "telefono_celular": lambda c: c.telefono,
        "telefono_residencial": lambda c: c.telefono,
        "pais_tributa": lambda c: "Panamá",
        "numero_tributario": lambda c: c.nit if c.nit else c.ruc if c.ruc else "",
        "es_pep_si": lambda c: "X" if c.es_pep else "",
        "es_pep_no": lambda c: "X" if not c.es_pep else "",
        "cargo_pep": lambda c: c.cargo if c.es_pep else "",
        "familiar_pep_si": lambda c: "",
        "familiar_pep_no": lambda c: "X",
        "nombre_pep_familiar": lambda c: "",
        "cargo_pep_familiar": lambda c: "",
        "relacion_pep": lambda c: "",
        "colaborador_pep_si": lambda c: "",
        "colaborador_pep_no": lambda c: "X",
        "nombre_pep_colaborador": lambda c: "",
        "cargo_pep_colaborador": lambda c: "",
        "relacion_pep_colaborador": lambda c: "",
        "ingreso_menos_10k": lambda c: "X" if c.ingresos_mensuales * 12 < 10000 else "",
        "ingreso_10k_30k": lambda c: "X" if 10000 <= c.ingresos_mensuales * 12 < 30000 else "",
        "ingreso_30k_50k": lambda c: "X" if 30000 <= c.ingresos_mensuales * 12 < 50000 else "",
        "ingreso_mas_50k": lambda c: "X" if c.ingresos_mensuales * 12 >= 50000 else "",
        "otros_ingresos_detalle": lambda c: "",
        "otros_ingresos_monto": lambda c: "",
        "profesion": lambda c: c.ocupacion,
        "ocupacion": lambda c: c.ocupacion,
        "nombre_empresa": lambda c: c.empresa,
        "telefono_empresa": lambda c: c.telefono,
        "correo_empresa": lambda c: c.email,
        "direccion_empresa": lambda c: c.direccion_completa,
        "actividad_independiente": lambda c: c.ocupacion if c.empresa and "independiente" in c.empresa.lower() else "",
        "nombre_firmante": lambda c: c.nombre_completo,
        "firma_fecha": lambda c: datetime.now().strftime("%d/%m/%Y"),
    }
}

# Templates por defecto
TEMPLATES_DEFAULT = {
    "morgan_morgan_natural": os.getenv("TEMPLATE_MORGAN_NATURAL"),
    "morgan_morgan_juridica": os.getenv("TEMPLATE_MORGAN_JURIDICA"),
    "mmg_bank": os.getenv("TEMPLATE_MMG_BANK"),
    "seguros_generico": os.getenv("TEMPLATE_SEGUROS"),
}

# ============= FUNCIONES AUXILIARES =============

def descargar_template(url: str, institucion: str) -> str:
    """Descarga el PDF template desde URL"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, 
            suffix='.pdf',
            prefix=f'{institucion}_template_'
        )
        temp_file.write(response.content)
        temp_file.close()
        
        return temp_file.name
    except Exception as e:
        raise HTTPException(500, f"Error descargando template: {str(e)}")

def mapear_datos(cliente: ClienteKYC, institucion: str) -> Dict[str, str]:
    """Mapea los datos del cliente según la institución"""
    mapeo = MAPEOS_INSTITUCIONES.get(institucion)
    
    if not mapeo:
        raise HTTPException(
            400, 
            f"Institución '{institucion}' no configurada. Disponibles: {list(MAPEOS_INSTITUCIONES.keys())}"
        )
    
    datos_mapeados = {}
    for campo_pdf, funcion_mapeo in mapeo.items():
        try:
            valor = funcion_mapeo(cliente)
            datos_mapeados[campo_pdf] = str(valor) if valor else ""
        except Exception as e:
            print(f"Error mapeando campo {campo_pdf}: {e}")
            datos_mapeados[campo_pdf] = ""
    
    return datos_mapeados

def llenar_pdf(template_path: str, datos: Dict[str, str], output_path: str) -> dict:
    """Llena el PDF con los datos mapeados"""
    try:
        pdf = PdfWrapper(template_path)
        
        # Intentar obtener campos disponibles
        try:
            campos_disponibles = list(pdf.schema.keys()) if hasattr(pdf, 'schema') else []
        except:
            campos_disponibles = list(datos.keys())
        
        # Filtrar solo campos que existen en el PDF
        datos_filtrados = {k: v for k, v in datos.items() if k in campos_disponibles}
        
        # Rellenar
        pdf.fill(datos_filtrados)

        # CAMBIO AQUÍ:
        with open(output_path, "wb+") as output:
            output.write(pdf.read())
        
        # Información de llenado
        campos_llenados = len(datos_filtrados)
        campos_faltantes = [k for k in datos.keys() if k not in campos_disponibles]
        
        return {
            "campos_llenados": campos_llenados,
            "total_campos": len(datos),
            "campos_no_encontrados": campos_faltantes,
            "porcentaje_completado": (campos_llenados / len(datos) * 100) if datos else 0
        }
        
    except Exception as e:
        raise HTTPException(500, f"Error rellenando PDF: {str(e)}")

# ============= ENDPOINTS =============

@app.get("/")
def root():
    return {
        "servicio": "KYC PDF Filler Panama",
        "version": "2.0.0",
        "instituciones_disponibles": list(MAPEOS_INSTITUCIONES.keys()),
        "formularios": [
            {"id": "morgan_morgan_natural", "nombre": "Morgan & Morgan - Persona Natural"},
            {"id": "morgan_morgan_juridica", "nombre": "Morgan & Morgan - Persona Jurídica"},
            {"id": "mmg_bank", "nombre": "MMG Bank - Persona Natural"},
            {"id": "seguros_generico", "nombre": "Seguros Genérico - Persona Natural"}
        ]
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/instituciones")
def listar_instituciones():
    """Lista todas las instituciones configuradas"""
    return {
        "instituciones": [
            {
                "id": key,
                "nombre": key.replace("_", " ").title(),
                "campos": len(mapeo)
            }
            for key, mapeo in MAPEOS_INSTITUCIONES.items()
        ]
    }

@app.post("/api/fill-form")
async def fill_form(request: FormularioRequest):
    """
    Endpoint principal para rellenar formularios KYC
    """
    try:
        # 1. Validar institución
        if request.institucion not in MAPEOS_INSTITUCIONES:
            raise HTTPException(
                400,
                f"Institución no válida. Use una de: {list(MAPEOS_INSTITUCIONES.keys())}"
            )
        
        # 2. Obtener template URL
        template_url = request.template_url or TEMPLATES_DEFAULT.get(request.institucion)
        
        if not template_url:
            raise HTTPException(
                400,
                f"No hay template configurado para {request.institucion}. Proporcione template_url"
            )
        
        # 3. Descargar template
        print(f"Descargando template de {template_url}...")
        template_path = descargar_template(template_url, request.institucion)
        
        # 4. Mapear datos del cliente
        print(f"Mapeando datos para {request.institucion}...")
        datos_mapeados = mapear_datos(request.cliente, request.institucion)
        
        # 5. Crear PDF de salida
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{request.institucion}_{request.cliente.cedula}_{timestamp}.pdf"
        output_path = f"/tmp/{output_filename}"
        
        # 6. Rellenar PDF
        print(f"Rellenando PDF...")
        info_llenado = llenar_pdf(template_path, datos_mapeados, output_path)
        
        # Limpiar archivos temporales
        os.unlink(template_path)
        
        return {
            "success": True,
            "institucion": request.institucion,
            "cliente": request.cliente.nombre_completo,
            "filename": output_filename,
            "filepath": output_path,
            "estadisticas": info_llenado,
            "timestamp": timestamp
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error procesando formulario: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
