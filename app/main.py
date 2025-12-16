""" Command to run the API: uvicorn app.main:app --reload
    Server: http://127.0.0.1:8000
    Home page: http://127.0.0.1:8000/hello """

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
    from app.build_summary import build_travel_summary_smart
    print("Build summary imported correctly \n")
except ImportError as e:
    print(f"ImportError: {e} \n")

print(f"\n Current working directory: {Path.cwd()} \n")

#*******************************************************************************
# FastAPI instance:
#*******************************************************************************

app = FastAPI()

#*******************************************************************************
# ImportantPaths:
#*******************************************************************************

PATH_APP = Path(__file__).resolve().parent # Path to the current file directory.
PATH_BASE_DIR = PATH_APP.parent # Path to the base directory of the project. 
PATH_UPLOADS = PATH_BASE_DIR / r"data/Uploads" # Relative path where the uploaded videos are stored.
PATH_OUTPUT = PATH_BASE_DIR / r"data/Output" # Relative path where the output videos are stored.


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
async def process_videos(request: Request, 
                         videos: list[UploadFile] = File(...),
                         music: UploadFile | None = File(None)):
    
    session_id = str(uuid.uuid4())
    session_dir = PATH_UPLOADS / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Guardar los videos subidos
    video_files = []
    for idx, vid in enumerate(videos):
        # prefijo según el orden de selección
        prefijo = f"{idx:03d}"  # 000, 001, 002, ...
        safe_name = f"{prefijo}_{vid.filename}"
        out_path = session_dir / safe_name

        with open(out_path, "wb") as f:
            shutil.copyfileobj(vid.file, f)

        video_files.append(out_path)
        
    # Guardar música (si viene)
    music_path = None
    if music is not None:
        music_path = session_dir / music.filename
        with open(music_path, "wb") as f:
            shutil.copyfileobj(music.file, f)

    # Carpeta output por sesión
    out_video_path = PATH_OUTPUT / f"{session_id}.mp4"

    # Llamamos a tu motor
    build_travel_summary_smart(
        video_dir=session_dir,
        output_path=out_video_path,
        bg_music_path=music_path
    )

    return templates.TemplateResponse("result.html", {
        "request": request,
        "output_video": f"/download/{session_id}"
    })

#-------------------------------------------------------------------------------

@app.get("/download/{video_id}")
def download_video(video_id: str):
    out_path = PATH_OUTPUT / f"{video_id}.mp4"
    if not out_path.exists():
        return {"error": "Archivo no encontrado"}
    return FileResponse(path=out_path, media_type="video/mp4", filename="travel_summary.mp4")
