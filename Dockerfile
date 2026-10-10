# Docker utiliza el . y el : como portal entre el disco y el contenedor; el . significa "derectorio actual" 
#  y el : significa el puente entre disco y contenedor
# si empieza con / entonces el directorio que quiere acceder no es el del disco, sino el del contenedor

#tpim4 es el nombre de la carpeta raiz del proyecto dentro del contenedor, app es una subcarpeta
#tambien es dentro del contenedor

# Usar la imagen oficial de Python (versión ligera)
FROM python:3.11-slim

# el string seguido de / es el nombre de la carpeta dentro del linux que utiliza docker para realizar el contenedor
# es decir sera el nombre de la carpeta raiz
WORKDIR /tpim4

# Copiar dependencias e instalarlas
COPY ./requirements.txt /tpim4/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /tpim4/requirements.txt

# Copiar la carpeta app hacia adentro del contenedor
COPY ./app /tpim4/app
#como app tendra el codigo fuente, mencionamos que pasemos el codigo fuente que se desarrolla en disco al contenedor
# de esta manera solo usamos docker para correr el codigo fuente, no para desarrollarlo
# ya que si lo hacemos dentro del contenedor, al salir del contenedor se perderia todo el codigo fuente desarrollado

# Iniciar Uvicorn usando la forma "exec" oficial, el cual se interpreta que "prende el servidor" y lo 
#deja corriendo en el contenedor, escuchando en el puerto 8000, aceptando cualquier host, que le inyectaremos luego
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
#el segundo parametro, menciona que le pasamos el archivo main que se encuentra en app, y le diremos que reciba app, cual 
#es el nombre de la variable que contiene la instancia de fastapi, que es la que se va a ejecutar 
#y que es la que contiene todas las rutas de la api