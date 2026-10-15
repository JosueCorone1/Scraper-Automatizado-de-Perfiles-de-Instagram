Instagram Data Scraper - Arquitectura Híbrida de Extracción

1. Descripción del Proyecto

Este proyecto consiste en un sistema automatizado de extracción de datos (Web Scraping) diseñado para recopilar información estructurada de perfiles de Instagram, incluyendo biografías, métricas de seguidores, publicaciones y contenido multimedia.

Desarrollado como proyecto práctico para la asignatura de Arquitectura de Software en la carrera de Ingeniería en Sistemas de Información de la Universidad Central del Ecuador, el sistema aborda los desafíos técnicos de interactuar con plataformas que poseen estrictas barreras de seguridad y prevención de bots.

2. Decisiones Arquitectónicas y Retos Técnicos (Limitaciones)

Durante el desarrollo, la plataforma de Meta bloqueó activamente las conexiones automatizadas devolviendo el Error HTTP 429 (Too Many Requests). Esto ocurre porque Instagram implementa validaciones de TLS Fingerprinting, detectando que las peticiones provienen de librerías HTTP (como Scrapy o Requests) y no de un navegador humano.

Para solventar esto, la arquitectura se dividió en dos enfoques:

Enfoque 1 (Pruebas Locales / Patrón Mocking): Se utilizó el framework Scrapy para construir el pipeline de extracción. Ante el bloqueo de red, se implementó el Patrón de Simulación (Mocking) leyendo un archivo mock_instagram.json local. Esto permite aislar la infraestructura externa y demostrar que la lógica interna de parseo y generación de diccionarios funciona correctamente.

Enfoque 2 (Evasión / Browser Automation): Se escaló la arquitectura utilizando Selenium. En lugar de peticiones HTTP puras, el sistema instancia un navegador Google Chrome real e inyecta código asíncrono en JavaScript (Fetch) utilizando la sesión (sessionid) del usuario. Esto unifica la huella digital criptográfica, logrando evadir los firewalls y descargar los datos estructurados en formato JSON.

3. Tecnologías Utilizadas

Lenguaje: Python 3.x

Framework de Scraping: Scrapy (para estructuración y pipelines)

Automatización de Navegador: Selenium WebDriver

Peticiones HTTP: Requests (para descarga de archivos multimedia)

Manejo de Datos: JSON

4. Requisitos Previos e Instalación

Para ejecutar este proyecto, es necesario tener instalado Python y Google Chrome en su equipo.

Clonar o descargar el repositorio.

Abrir una terminal en la carpeta del proyecto.

Instalar las dependencias requeridas ejecutando:

pip install scrapy selenium requests


5. Instrucciones de Ejecución

El proyecto ofrece dos métodos de ejecución dependiendo del estado de la red y el "Rate Limiting" de la cuenta:

Opción A: Extracción Real (Selenium + JS Fetch)

Este método interactúa con los servidores reales de Instagram utilizando una huella de navegador válida.

Abra una ventana de incógnito en Google Chrome e inicie sesión en Instagram.

Extraiga sus cookies frescas (sessionid y csrftoken).

Inserte estas credenciales en la sección de CONFIGURACIÓN del archivo instagram_scraper_completo.py.

Ejecute el script:

python instagram_scraper_completo.py


Opción B: Entorno Simulado (Mocking con Scrapy)

Ideal para pruebas de desarrollo o cuando la dirección IP se encuentra en estado de penalización (Error 429).

Asegúrese de tener el archivo mock_instagram.json en el mismo directorio.

Verifique que la variable start_urls en instagram_spider.py apunte al archivo local (file:///...).

Ejecute el spider para procesar el Mock:

python -m scrapy runspider instagram_spider.py -o datos_perfil.json


6. Estructura de Salida (Output)

La ejecución exitosa del sistema generará una carpeta llamada instagram_export/ (o un archivo datos_perfil.json en el caso del Mock) que contendrá datos limpios y estructurados como:

perfil.json: Datos biográficos y métricas principales.

publicaciones.json: Lista de los últimos posts, likes, y descripciones.

seguidores.json / seguidos.json: Nodos de la red de contactos.

7. Autor

Jhonatan Josue Coronel Herrera

Estudiante de Ingeniería en Sistemas de Información

Universidad Central del Ecuador

Asignatura: Arquitectura de Software
