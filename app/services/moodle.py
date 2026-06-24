from pathlib import Path
from urllib.parse import urljoin

import httpx

from app.config import settings


class MoodleDownloadError(RuntimeError):
    pass


class MoodleClient:
    def __init__(self) -> None:
        self.base_url = settings.moodle_base_url.rstrip("/")
        if settings.moodle_service_path.startswith(("http://", "https://")):
            self.service_url = settings.moodle_service_path
        else:
            self.service_url = urljoin(self.base_url, settings.moodle_service_path)
        self.token = settings.moodle_token

    async def download_submission_pdf(
        self,
        cmid: int,
        user_id: int,
        course_id: int,
        target_dir: Path,
    ) -> Path:
        if not self.token or self.token.strip().lower().startswith("coloca_"):
            raise MoodleDownloadError("Falta configurar un MOODLE_TOKEN real en .env.")

        target_dir.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=60) as client:
            module = await self._find_course_module(client, course_id, cmid)
            file_url = await self._find_submission_file_url(client, module, user_id)
            return await self._download_file(client, file_url, target_dir, cmid, user_id)

    async def _call(self, client: httpx.AsyncClient, wsfunction: str, params: dict) -> dict | list:
        try:
            response = await client.post(
                self.service_url,
                data={
                    "wstoken": self.token,
                    "moodlewsrestformat": "json",
                    "wsfunction": wsfunction,
                    **params,
                },
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise MoodleDownloadError(
                f"No se pudo conectar con Moodle en {self.service_url}. "
                "Revisa MOODLE_BASE_URL, el puerto, la red/firewall y que Moodle este publicado."
            ) from exc
        except httpx.TimeoutException as exc:
            raise MoodleDownloadError(
                f"Moodle no respondio a tiempo en {self.service_url}."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise MoodleDownloadError(
                f"Moodle respondio HTTP {exc.response.status_code} al llamar {wsfunction}."
            ) from exc

        payload = response.json()
        if isinstance(payload, dict) and payload.get("exception"):
            raise MoodleDownloadError(payload.get("message", "Error de Moodle."))
        return payload

    async def _find_course_module(
        self,
        client: httpx.AsyncClient,
        course_id: int,
        cmid: int,
    ) -> dict:
        contents = await self._call(client, "core_course_get_contents", {"courseid": course_id})
        for section in contents:
            for module in section.get("modules", []):
                if int(module.get("id", 0)) == cmid:
                    return module
        raise MoodleDownloadError(f"No se encontro el cmid {cmid} en el curso {course_id}.")

    async def _find_submission_file_url(
        self,
        client: httpx.AsyncClient,
        module: dict,
        user_id: int,
    ) -> str:
        module_name = module.get("modname")
        instance_id = module.get("instance")

        if module_name == "assign" and instance_id:
            submissions = await self._call(
                client,
                "mod_assign_get_submissions",
                {"assignmentids[0]": int(instance_id)},
            )
            for assignment in submissions.get("assignments", []):
                for submission in assignment.get("submissions", []):
                    if int(submission.get("userid", 0)) != user_id:
                        continue
                    for plugin in submission.get("plugins", []):
                        for area in plugin.get("fileareas", []):
                            for file_item in area.get("files", []):
                                file_url = file_item.get("fileurl", "")
                                filename = file_item.get("filename", "").lower()
                                if file_url and filename.endswith(".pdf"):
                                    return file_url

        for content in module.get("contents", []):
            file_url = content.get("fileurl", "")
            filename = content.get("filename", "").lower()
            if file_url and filename.endswith(".pdf"):
                return file_url

        raise MoodleDownloadError(
            "No se encontro un PDF para ese usuario. Revisa permisos del token o el tipo de actividad."
        )

    async def _download_file(
        self,
        client: httpx.AsyncClient,
        file_url: str,
        target_dir: Path,
        cmid: int,
        user_id: int,
    ) -> Path:
        separator = "&" if "?" in file_url else "?"
        authed_url = f"{file_url}{separator}token={self.token}"
        target_path = target_dir / f"moodle_{cmid}_{user_id}.pdf"

        try:
            response = await client.get(authed_url)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise MoodleDownloadError(
                f"No se pudo descargar el archivo desde Moodle. URL base: {self.base_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise MoodleDownloadError("La descarga del PDF desde Moodle excedio el tiempo de espera.") from exc
        except httpx.HTTPStatusError as exc:
            raise MoodleDownloadError(
                f"Moodle respondio HTTP {exc.response.status_code} al descargar el PDF."
            ) from exc

        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type.lower() and not response.content.startswith(b"%PDF"):
            raise MoodleDownloadError("Moodle respondio, pero el archivo descargado no parece PDF.")

        max_bytes = settings.max_pdf_mb * 1024 * 1024
        if len(response.content) > max_bytes:
            raise MoodleDownloadError(f"El PDF supera el limite de {settings.max_pdf_mb} MB.")

        target_path.write_bytes(response.content)
        return target_path
