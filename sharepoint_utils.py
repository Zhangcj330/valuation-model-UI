from typing import List, Dict, Union, BinaryIO
import streamlit as st
import io
import requests
import app_config


class SharePointClient:
    def __init__(self):
        """Initialize SharePoint client using user's access token"""
        if not st.session_state.get("token"):
            raise ValueError("No authentication token found in session state")

        self.token = st.session_state.token["access_token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        self.base_url = "https://graph.microsoft.com/v1.0"

        # Get SharePoint site ID if not provided
        if not app_config.SHAREPOINT_SITE_ID:
            self.site_id = self._get_site_id()
        else:
            self.site_id = app_config.SHAREPOINT_SITE_ID

    def _get_site_id(self) -> str:
        """Get SharePoint site ID using REST API"""
        site_name = app_config.SHAREPOINT_SITE_NAME
        if "/" not in site_name:
            url = f"{self.base_url}/sites/root:/sites/{site_name}"
        else:
            hostname = site_name.split("/")[0]
            site_path = "/".join([""] + site_name.split("/")[1:])
            url = f"{self.base_url}/sites/{hostname}:{site_path}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            site_data = response.json()
            return site_data["id"]
        except Exception as e:
            raise Exception(f"Failed to get site ID: {str(e)}")

    def list_files(self, folder_path: str = "") -> List[str]:
        """List Excel files in SharePoint folder"""
        folder_path = folder_path.lstrip("/")
        url = f"{self.base_url}/sites/{self.site_id}/drive/root"

        if folder_path:
            url += f":/{folder_path}:/children"
        else:
            url += "/children"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            items = response.json().get("value", [])

            files = []
            for item in items:
                if "folder" not in item:  # If not a folder
                    name = item["name"]
                    if name.endswith(".xlsx"):
                        files.append(name.replace(".xlsx", ""))

            return sorted(files)
        except Exception as e:
            raise Exception(f"Error listing files: {str(e)}")

    def list_folders(self, folder_path: str = "") -> List[str]:
        """List subfolders in SharePoint folder"""
        folder_path = folder_path.lstrip("/")
        url = f"{self.base_url}/sites/{self.site_id}/drive/root"

        if folder_path:
            url += f":/{folder_path}:/children"
        else:
            url += "/children"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            items = response.json().get("value", [])

            folders = []
            for item in items:
                if "folder" in item:  # If it's a folder
                    folders.append(item["name"])

            return sorted(folders)
        except Exception as e:
            raise Exception(f"Error listing folders: {str(e)}")

    def download_file(self, file_path: str) -> BinaryIO:
        """Download file from SharePoint"""
        file_path = file_path.lstrip("/")
        url = f"{self.base_url}/sites/{self.site_id}/drive/root:/{file_path}:/content"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return io.BytesIO(response.content)
        except Exception as e:
            raise Exception(f"Error downloading file: {str(e)}")

    def upload_file(self, content: Union[str, bytes], target_path: str) -> str:
        """Upload file to SharePoint"""
        target_path = target_path.lstrip("/")

        if isinstance(content, str):
            content = content.encode("utf-8")

        # For small files (< 4MB), use simple upload
        if len(content) < 4 * 1024 * 1024:
            url = f"{self.base_url}/sites/{self.site_id}/drive/root:/{target_path}:/content"
            try:
                response = requests.put(
                    url,
                    headers={
                        **self.headers,
                        "Content-Type": "application/octet-stream",
                    },
                    data=content,
                )
                response.raise_for_status()
                return target_path
            except Exception as e:
                raise Exception(f"Error uploading file: {str(e)}")

        # For larger files, use upload session
        try:
            # Create upload session
            url = f"{self.base_url}/sites/{self.site_id}/drive/root:/{target_path}:/createUploadSession"
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            upload_url = response.json()["uploadUrl"]

            # Upload in chunks
            chunk_size = 320 * 1024  # 320 KB chunks
            for i in range(0, len(content), chunk_size):
                chunk = content[i : i + chunk_size]
                content_range = f"bytes {i}-{i+len(chunk)-1}/{len(content)}"

                response = requests.put(
                    upload_url,
                    headers={
                        "Content-Length": str(len(chunk)),
                        "Content-Range": content_range,
                    },
                    data=chunk,
                )
                response.raise_for_status()

            return target_path
        except Exception as e:
            raise Exception(f"Error uploading large file: {str(e)}")

    def get_folder_structure(self, root_folder: str = "") -> Dict[str, Dict]:
        """Get complete folder structure"""
        structure = {}
        folders = self.list_folders(root_folder)

        for folder in folders:
            folder_path = f"{root_folder}/{folder}".lstrip("/")
            structure[folder] = {
                "files": self.list_files(folder_path),
                "subfolders": self.get_folder_structure(folder_path),
            }

        return structure

    def get_file_url(self, file_path: str) -> str:
        """
        Get SharePoint web URL for a file

        Args:
            file_path: Path to file in SharePoint

        Returns:
            Web URL for the file
        """
        file_path = file_path.lstrip("/")
        response = requests.get(
            f"{self.base_url}/sites/{self.site_id}/drive/root:/{file_path}:/webUrl",
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()["webUrl"]
