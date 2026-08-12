from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
import requests
import subprocess
import tempfile
import os
import re

app = FastAPI(title="Kyotei AI API")


@app.get("/")
def health():
    return {
        "status": "ok",
        "message": "Kyotei AI API is running"
    }


@app.get("/program", response_class=PlainTextResponse)
def get_program(
    date: str = Query(..., description="YYYYMMDD")
):
    # 日付は8桁の数字だけ許可
    if not re.fullmatch(r"\d{8}", date):
        raise HTTPException(
            status_code=400,
            detail="date must be YYYYMMDD"
        )

    yy = date[2:4]
    mm = date[4:6]
    dd = date[6:8]

    # BOAT RACE公式の番組表LZH
    url = (
        f"https://www1.mbrace.or.jp/od2/B/"
        f"{date[:6]}/b{yy}{mm}{dd}.lzh"
    )

    try:
        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )
        response.raise_for_status()

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(
                temp_dir,
                f"b{yy}{mm}{dd}.lzh"
            )

            with open(archive_path, "wb") as f:
                f.write(response.content)

            # LhasaでLZHを展開
            result = subprocess.run(
                ["lha", "-xq2", archive_path],
                cwd=temp_dir,
                capture_output=True,
                timeout=30
            )

            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail="LZH decompression failed"
                )

            txt_files = [
                file
                for file in os.listdir(temp_dir)
                if file.lower().endswith(".txt")
            ]

            if not txt_files:
                raise HTTPException(
                    status_code=500,
                    detail="TXT file not found in archive"
                )

            txt_path = os.path.join(
                temp_dir,
                txt_files[0]
            )

            with open(txt_path, "rb") as f:
                raw = f.read()

            # 公式TXTは日本語のためCP932として読み込み
            text = raw.decode(
                "cp932",
                errors="replace"
            )

            return text

    except requests.RequestException as e:
        raise HTTPException(
            status_code=502,
            detail=f"BOAT RACE data download failed: {str(e)}"
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=500,
            detail="LZH decompression timed out"
        )
