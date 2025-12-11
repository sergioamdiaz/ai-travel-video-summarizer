#*******************************************************************************
# Imports:
#*******************************************************************************

from pathlib import Path
import shutil
import uuid

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

try:
    from app.video_processor import build_travel_summary
    print("El módulo se importó correctamente. \n")
except ImportError as e:
    print(f"Error al importar: {e} \n")

print(f"\n Current working directory: {Path.cwd()} \n")

#*******************************************************************************
# FastAPI instance:
#*******************************************************************************
app = FastAPI()

#*******************************************************************************
# ImportantPaths:
#*******************************************************************************

PATH_APP = Path(__file__).resolve().parent # Path to the current file.
PATH_BASE_DIR = PATH_APP.parent # Path to the base directory of the project. 
PATH_UPLOADS = PATH_BASE_DIR / r"data/uploads" # Relative path where the uploaded videos are stored.
PATH_CONCATS = PATH_BASE_DIR / r"data/concatenated" # Relative path where the concatenated videos are stored.

print(f"- Path File Dir: {PATH_APP}") # app folder
print(f"- Path Base Dir: {PATH_BASE_DIR}")
print(f"- Path Uploads Dir: {PATH_UPLOADS}")
print(f"- Path Concats Dir: {PATH_CONCATS}")

#*******************************************************************************
# Templates + Static Files:
#*******************************************************************************
templates = Jinja2Templates(directory=str(PATH_APP / "templates")) # Where the templates are stored.
app.mount("/static", StaticFiles(directory=str(PATH_APP / "static")), name="static")

#*******************************************************************************
# Body:
#*******************************************************************************

@app.get("/hello", response_class=HTMLResponse) # When the user goes to the home page (http://127.0.0.1:8000/hello), the browser always executes a GET. ("hello" is just an arbitrary name, normally it is just "/").
def upload_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

#-------------------------------------------------------------------------------

@app.post("/YourVideoIsReady")
async def process_videos(request: Request, videos: list[UploadFile] = File(...)):
    session_id = str(uuid.uuid4())
    session_dir = PATH_UPLOADS / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Guardar los videos subidos
    video_files = []
    for vid in videos:
        out_path = session_dir / vid.filename
        with open(out_path, "wb") as f:
            shutil.copyfileobj(vid.file, f)
        video_files.append(out_path)

    # Carpeta output por sesión
    out_video_path = PATH_CONCATS / f"{session_id}.mp4"

    # Llamamos a tu motor
    build_travel_summary(
        video_folder=session_dir,
        export_path=out_video_path
    )

    return templates.TemplateResponse("result.html", {
        "request": request,
        "output_video": f"/download/{session_id}"
    })

#-------------------------------------------------------------------------------

@app.get("/download/{video_id}")
def download_video(video_id: str):
    out_path = PATH_CONCATS / f"{video_id}.mp4"
    if not out_path.exists():
        return {"error": "Archivo no encontrado"}
    return FileResponse(path=out_path, media_type="video/mp4", filename="travel_summary.mp4")
