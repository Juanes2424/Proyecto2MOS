#### Como correr el codigo?

Nuestra implementacion utiliza para los datos de distancia y visualizaciones. Esto se debe a la facilidad para crear mapas con direcciones y la posibilidad de hacer muchas (10,000) consultas al API de manera gratuita. 

Para correr el codigo se necesita crear una llave de Google Maps con el instructivo disponible en: https://developers.google.com/maps/documentation/javascript/get-api-key

Posteriormente se debe pegar en la variable de main.py global dispuesta para ello.

Tan pronto inicia la ejecucion del programa hay dos opciones, la segunda permite consultar directamente al API y posteriormente se guarda un csv (distances.csv) con la matriz de distancias. La opcion 1 permite tomar distances.csv como punto de partida. Esto se realizo con el objetivo de no sobre consultar al API generando costos adicionales.

Al finalizar la ejecucion por consola se ven las rutas de cada vehiculo y se genera un html en la raiz del proyecto donde se visualizan las rutas.

#### Estructura

Existe una carpeta llamada content donde se encuentran los csv's. Adicionalmente en la raiz se ve main.py que maneja todo en cuanto a codigo y se encuentra un html para la visualizacion. Los archivos csv de verificacion se encunetran en la carpeta verificaciones.
