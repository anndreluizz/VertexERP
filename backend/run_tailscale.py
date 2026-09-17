import uvicorn
from app.core.tls import garantir_certificado
from main import app

cert, key = garantir_certificado("certs")
uvicorn.run(app, host="0.0.0.0", port=8000, ssl_certfile=cert, ssl_keyfile=key)
