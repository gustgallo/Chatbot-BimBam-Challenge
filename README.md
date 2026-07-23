# BimBam Buy - Lector de Documentos PDF con IA (Cohere Chatbot)

Un chatbot interactivo y moderno impulsado por Inteligencia Artificial para la lectura, extracción y consulta en lenguaje natural de fuentes documentales en formato PDF. Desarrollado específicamente para el ecosistema de e-commerce **BimBam Buy**.

## URL Despliegue de Proyecto

https://chatbot-bim-bam-challenge.vercel.app/

---

##  Descripción General

**BimBam Buy** es un e-commerce multiplataforma enfocado en brindar una experiencia de compra digital ágil y segura. Destaca por su modelo orientado al cliente, con políticas robustas de reembolso, un programa de afiliados dinámico y una infraestructura logística optimizada para garantizar entregas rápidas y soporte constante.

Este proyecto implementa una solución de **Generación Aumentada por Recuperación (RAG - Retrieval-Augmented Generation)** utilizando la API de **Cohere AI**. Permite a los usuarios seleccionar o subir documentos PDF oficiales de la empresa (políticas de reembolso, garantías, métodos de pago, envíos y afiliados) y realizar preguntas complejas en lenguaje natural desde una interfaz web fluida y atractiva.

---

##  Arquitectura de la Solución

El sistema cuenta con una arquitectura desacoplada organizada de la siguiente manera:

```
┌─────────────────────────────────────────────────────────┐
│              Interfaz Web (HTML5 / CSS / JS)            │
│  - Columna Derecha: Gestión & Selección de Fuentes PDF   │
│  - Área Central: Chat interactivo & Sugerencias         │
└───────────────────────────┬─────────────────────────────┘
                            │ (HTTP / JSON REST API)
┌───────────────────────────▼─────────────────────────────┐
│                 Servidor Backend (Flask)                │
│                     [app.py]                            │
└─────────────┬─────────────────────────────┬─────────────┘
              │                             │
┌─────────────▼─────────────┐ ┌─────────────▼─────────────┐
│  Extractor y Chunking PDF │ │  Cohere RAG & Chat Engine │
│   [pdf_processor.py]      │ │    [cohere_service.py]    │
│  - Extracción con PyPDF   │ │ - Embeddings Multilingual │
│  - Sliding Window Chunk   │ │ - Cosine Similarity Search│
│                           │ │ - Command-R / Command-R+  │
└───────────────────────────┘ └───────────────────────────┘
```

### Flujo de Datos (RAG Step-by-Step):
1. **Indexación y Fragmentación**: Al iniciar el servidor o subir un nuevo PDF, `pdf_processor.py` extrae el texto por páginas y lo divide en *chunks* (fragmentos con solapamiento) preservando metadatos como nombre de archivo y número de página.
2. **Generación de Embeddings**: Al enviar una consulta, `cohere_service.py` utiliza el modelo `embed-multilingual-v3.0` de Cohere para vectorizar tanto la pregunta del usuario como los fragmentos de los PDFs activos.
3. **Búsqueda Vectorial**: Se calcula la similitud cosenoidal entre el vector de la consulta y los vectores de los documentos, seleccionando los 5 fragmentos más relevantes.
4. **Generación con Citas**: Los fragmentos seleccionados se envían al modelo `command-r-08-2024` o `command-r-plus` junto con instrucciones del sistema en español. El modelo genera una respuesta precisa y cita el documento y número de página correspondiente.

---

##  Tecnologías y Herramientas

### Backend (Lógica del Sistema)
- **Python 3.9+**: Lenguaje principal de desarrollo backend.
- **Flask & Flask-CORS**: Framework web ligero para la exposición de endpoints REST API.
- **Cohere SDK (`cohere`)**: Integración con modelos LLM de última generación para RAG y Chat.
- **PyPDF**: Extracción rápida y precisa de texto desde archivos PDF.
- **NumPy**: Cálculo optimizado de similitud cosenoidal para vectores de embeddings.
- **Python-Dotenv**: Manejo seguro de variables de entorno (`.env`).

### Frontend (Interfaz de Usuario)
- **HTML5 Semántico**: Estructura limpia y accesible.
- **Vanilla CSS3**: Diseño personalizado en modo oscuro (*Midnight Glassmorphism*), gradientes fluidos y micro-animaciones sin dependencias externas pesadas.
- **Vanilla JavaScript (ES6+)**: Consumo asíncrono de la API REST (`fetch`), gestión dinámica del historial de chat, drag & drop de archivos y selección interactiva de fuentes.
- **Google Fonts & FontAwesome**: Tipografía profesional (`Plus Jakarta Sans` / `JetBrains Mono`) e iconografía moderna.

---

##  Instrucciones para Ejecutar el Proyecto

### Requisitos Previos
- Tener instalado **Python 3.9** o superior.
- Una clave de API de Cohere (puedes obtener una gratuita en [dashboard.cohere.com](https://dashboard.cohere.com/api-keys)).

### Paso 1: Clonar o descargar la carpeta del proyecto
Asegúrate de estar ubicado en la directorio raíz del proyecto:
```bash
cd "c:/Users/CASA/Desktop/Proyecto Oracle/Proyecto 1"
```

### Paso 2: Crear e instalar el entorno virtual
```bash
# Crear entorno virtual (opcional pero recomendado)
python -m venv venv

# Activar entorno virtual en Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt
```

### Paso 3: Configurar la API Key de Cohere
Tienes dos opciones para proporcionar tu API Key:

#### Opción A: Archivo `.env` (Recomendado)
Crea un archivo llamado `.env` en la raíz del proyecto con la siguiente variable:
```env
COHERE_API_KEY=tu_api_key_aqui
```

#### Opción B: Desde la Interfaz Web
Si no configuras el archivo `.env`, puedes ingresar tu API Key directamente desde el botón **"API Key"** ubicado en la esquina superior derecha de la interfaz web.

### Paso 4: Iniciar el Servidor Backend
```bash
python app.py
```
El servidor se ejecutará en: `http://localhost:5000`

### Paso 5: Abrir la Aplicación Web
Abre tu navegador (Chrome, Edge, Firefox) e ingresa a:
 **`http://localhost:5000`**

---

##  Ejemplos de Preguntas que el Agente Puede Responder

Gracias a los 5 documentos institucionales incluidos de **BimBam Buy**, el agente responde preguntas como:

1. **Reembolsos**: *"¿Cuáles son los requisitos y el plazo máximo para solicitar la devolución de un producto comprando en BimBam Buy?"*
2. **Envíos y Logística**: *"¿Cuánto cuesta el envío exprés y qué cobertura geográfica tiene BimBam Buy?"*
3. **Programa de Afiliados**: *"¿Cómo funcionan las comisiones del Programa de Afiliados y cuándo se realizan los pagos?"*
4. **Métodos de Pago**: *"¿Qué medios de pago digitales son aceptados y cuál es el procedimiento de verificación de seguridad?"*
5. **Garantía de Productos**: *"¿Qué cubre la garantía de un equipo electrónico y qué documentos debo presentar para hacerla efectiva?"*

---

##  Ejemplos de Respuestas Generadas por el Agente

### Ejemplo 1: Consulta sobre Reembolsos y Devoluciones
> **Usuario**: *"¿Cuántos días tengo para solicitar un reembolso y cuáles son las condiciones?"*
>
> **BimBam Buy AI Agent**:
> El periodo para solicitar un reembolso en **BimBam Buy** es de **30 días calendario** a partir de la fecha de entrega del producto.
>
> **Condiciones principales**:
> - El artículo debe encontrarse en su empaque original sin sellos rotos.
> - Se debe adjuntar la factura electrónica o comprobante de compra.
> - El costo de envío del retorno es asumido por BimBam Buy si el producto presentó defectos de fábrica.
>
>  *Fuentes Citadas*: `Politicas de Reembolsos.pdf (Pág. 1)`

---

### Ejemplo 2: Consulta sobre Envíos y Tiempos de Entrega
> **Usuario**: *"¿Cuánto demora un envío estándar y cuál es el costo?"*
>
> **BimBam Buy AI Agent**:
> Para envíos estándar a nivel nacional, los tiempos de entrega estimados son de **2 a 4 días hábiles**. 
> 
> **Detalles de Costos**:
> - Envíos estándar: **Gratis** en compras superiores a $50 USD.
> - Compras menores a $50 USD: tarifa fija de **$4.99 USD**.
> - Envíos exprés (entrega en 24 horas): tarifa plana de **$9.99 USD**.
>
>  *Fuentes Citadas*: `Guía de Tiempos y Costos de Envío de BimBam Buy.pdf (Pág. 2)`

---

### Ejemplo 3: Consulta sobre el Programa de Afiliados
> **Usuario**: *"¿Cuál es la tasa de comisión para los afiliados de BimBam Buy?"*
>
> **BimBam Buy AI Agent**:
> El Programa de Afiliados de **BimBam Buy** ofrece una estructura de comisiones escalonada según la categoría del producto:
> 
> - **Electrónica y Tecnología**: 8% por venta realizada.
> - **Moda y Accesorios**: 12% por venta realizada.
> - **Hogar y Estilo de Vida**: 10% por venta realizada.
>
> Las comisiones se liquidan los días 15 de cada mes a través de transferencia bancaria o PayPal.
>
>  *Fuentes Citadas*: `Programa de Afiliados de BimBam.pdf (Pág. 1)`

---

##  Estructura del Proyecto

```
Proyecto 1/
├── app.py                                            # Servidor web Flask REST API
├── cohere_service.py                                 # Integración RAG & Cohere Chat Client
├── pdf_processor.py                                  # Módulo de extracción y chunking de PDFs
├── requirements.txt                                  # Lista de dependencias de Python
├── README.md                                         # Documentación general y arquitectura
├── Guía de Tiempos y Costos de Envío de BimBam Buy.pdf  # PDF institucional
├── Manual de Garantía de Productos de BimBam Buy.pdf    # PDF institucional
├── Politicas de Reembolsos.pdf                       # PDF institucional
├── Preguntas_Frecuentes_sobre_Métodos_de_Pago...pdf  # PDF institucional
├── Programa de Afiliados de BimBam.pdf               # PDF institucional
├── static/
│   ├── index.html                                    # Interfaz Web HTML5
│   ├── styles.css                                    # Estilos CSS Glassmorphism
│   └── app.js                                        # Lógica Cliente JS (Vanilla)
└── uploads/                                          # Archivos PDF subidos por usuarios
```

##  Deploy en Vercel

La aplicación fue desplegada en Vercel mediante la integración con GitHub. El proyecto utiliza Flask para el backend y la carpeta public para los archivos del frontend, como index.html, app.js y styles.css.

La configuración utilizada fue la siguiente:

Framework Preset: Flask
Root Directory: ./
Build Command: None
Output Directory: N/A

También se configuró la variable de entorno COHERE_API_KEY directamente en Vercel para evitar publicar información sensible dentro del repositorio.

Cada vez que se realiza un nuevo git push a la rama main, Vercel detecta los cambios y genera automáticamente un nuevo despliegue de la aplicación.



## Imagenes de Ejemplo aplicacion funcionando

<img width="1600" height="813" alt="image" src="https://github.com/user-attachments/assets/e4551297-8ca5-45fa-8c46-b743706d405a" />


<img width="1598" height="862" alt="image" src="https://github.com/user-attachments/assets/a4ee3505-ee29-408e-b304-80614ade7d52" />




