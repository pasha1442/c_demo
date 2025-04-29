import random
import threading
import requests
import boto3
from boto3.s3.transfer import TransferConfig
import pdfkit as pdf
from decouple import config
import json
import os
import re

from datetime import datetime, timedelta
from base64 import decodebytes
from django.core.validators import validate_ipv46_address
from django.conf import settings
from django.template.loader import render_to_string
from basics.decorators import Singleton
import shutil
import aiohttp
import asyncio
import random
import string
import uuid
import ulid

from datetime import datetime


@Singleton
class Registry:

    def __init__(self):
        self.tls = threading.local()
        setattr(self.tls, 'data', {})

    @property
    def _data(self):
        if not hasattr(self.tls, 'data'):
            setattr(self.tls, 'data', {})

        return self.tls.data

    def clear(self):
        setattr(self.tls, 'data', {})

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def has(self, key):
        return key in self._data

    def delete(self, key):
        if key in self._data:
            del self._data[key]


class UUID:

    @staticmethod
    def get_uuid():
        # unique_id = f"{str(uuid.uuid4())}"
        unique_id = f"{str(ulid.new())}"
        return unique_id

    @staticmethod
    def get_uuid4():
        unique_id = f"{str(uuid.uuid4())}"
        return unique_id


def generate_random_string(length):
    letters = string.ascii_letters  # Contains both lowercase and uppercase letters
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


def round_off_datetime(datetime_obj):
    """Round the datetime object to the nearest minute (set seconds to 0)"""
    return datetime_obj.replace(second=0, microsecond=0)


def check_mandatory_values(_dict, _list):
    _not_found = []
    for _item in _list:
        if not _dict.get(_item, None):
            _not_found.append(_item)
    return _not_found


def execute_in_background(function_body, *args):
    if isinstance(function_body, bool):
        function_body = lambda: function_body
    process_thread = threading.Thread(target=function_body, args=args)
    process_thread.start()


class FileHandling:

    @staticmethod
    def copy_file(source_path, destination_path):
        shutil.copy(source_path, destination_path)

    @staticmethod
    def get_data_file(path, tail_number=20):
        return os.popen(f"tail -n {tail_number} {path}").read()

    @staticmethod
    def check_path_exist(path):
        return os.path.isfile(path)

    @staticmethod
    def check_and_create_directories(path):
        is_path_exists = True if os.path.exists(path) else False

        if not is_path_exists:
            os.makedirs(path)
        return path

    @staticmethod
    def download_file(file_url, file_path):
        with requests.Session() as session:
            response = session.get(file_url)
            if response.status_code == 200:
                with open(file_path, 'wb') as file:
                    file.write(response.content)
                    file.close()
                return True
            else:
                return False

    @staticmethod
    async def get_file_from_url_using_async(url, destination):
        try:
            result = asyncio.Future()
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(destination, 'wb') as file:
                            file.write(content)
                            file.close()
                        result.set_result(True)
                    else:
                        result.set_result(False)
        except asyncio.TimeoutError:
            result.set_result(False)
        return result

    @staticmethod
    async def get_file_from_url(file_url, **kwargs):
        if file_url:
            split_delimiter = kwargs.get("split", False)
            path = kwargs.get("path")
            file_name = kwargs.get("file_name")
            FileHandling.check_and_create_directories(path)
            file_path = path + "/" + file_name
            # response = requests.head(file_url)
            # if response.status_code == 200:
            #     wget.download(file_url, out=file_path)
            # download = FileHandling.download_file(file_url, file_path)

            download = await FileHandling.get_file_from_url_using_async(file_url, file_path)

            await asyncio.gather(download)
            if download.result():
                return file_path.split(split_delimiter)[-1] if split_delimiter else file_path
            else:
                return False

    @staticmethod
    def get_date_based_path(root, folder, date_path=datetime.now()):
        path = str(root) + "/" + str(date_path.year) + "/" + str(date_path.month) + "/" + str(
            DateFormatter.format_date_time(date_path, '%d_%m_%Y')) + "/" + str(folder)
        return str(path)

    @staticmethod
    def delete_files(path_list):
        for path in path_list:
            try:
                os.remove(os.path.join(settings.MEDIA_ROOT, str(path)))
            except:
                pass

    @staticmethod
    def remove_file(file_path):
        if os.path.exists(file_path):
            os.remove(file_path)

    @staticmethod
    def dataframe_to_excel(df, file_path, header=""):
        df.to_excel(file_path, header=header)

    @staticmethod
    def dataframe_to_csv(df, file_path, header=""):
        df.to_csv(file_path, header=header)

    @staticmethod
    def dataframe_to_pdf(df, file_path, html_file='', extra_data={}):
        col_headers = df.columns.tolist()
        json_records = df.reset_index().to_json(orient="records", date_format="iso")
        data = json.loads(json_records)
        extra_data['columns'] = col_headers
        extra_data['loop_times'] = range(0, len(col_headers))
        data.append(extra_data)

        context = {'d': data}
        string = render_to_string(html_file, context)
        options = {
            'page-size': 'A4',
            'margin-bottom': '10mm',
            'margin-right': '5mm',
            'margin-left': '5mm',
            "enable-local-file-access": True
        }
        pdf.from_string(string, file_path, options=options)


class ImageConversion:
    @staticmethod
    def convert_string_to_image(string, **kwargs):
        if string and string.strip():
            split_delimiter = kwargs.get("split", False)
            path = kwargs.get("path")
            file_name = kwargs.get("file_name")
            bytecode = bytes(string, 'utf-8')
            FileHandling.check_and_create_directories(path)
            file_path = path + "/" + file_name
            with open(file_path, "wb") as f:
                f.write(decodebytes(bytecode))
                f.close()
            return file_path.split(split_delimiter)[-1] if split_delimiter else file_path
        
    @staticmethod
    def get_file_extension_from_base64_string(base64_string):
        # Returns 'png', 'jpeg', 'gif', etc.
        match = re.match(r"data:image/([a-zA-Z]+);base64,", base64_string)
        if match:
            return match.group(1)
        return None


class DataValidator:
    class Email:
        @staticmethod
        def is_valid_data(email):
            regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            if re.fullmatch(regex, email):
                return True, ""
            else:
                return False, "Invalid Email"

    class Ip:
        @staticmethod
        def is_valid_data(ip):
            try:
                validate_ipv46_address(ip)
                return True
            except:
                return False

    def validate_data(device_arg, _data_keys=[]):
        request_data, invalid_data, validate_func = device_arg, [], {"email": DataValidator.Email,
                                                                     "ip_address": DataValidator.Ip}
        for key in _data_keys:
            result = validate_func.get(key).is_valid_data(request_data.get(key))
            if not result:
                invalid_data.append(key)
        return invalid_data


class DateTimeConversion:

    @staticmethod
    def to_string(_datetime_obj, format="%Y-%m-%d %H:%M:%S"):
        str_datetime = _datetime_obj.strftime(format)
        return str_datetime

    @staticmethod
    def str_to_datetime(_datetime_str, format="%Y-%m-%d %H:%M:%S"):
        _datetime = datetime.strptime(_datetime_str, format)
        return _datetime


class EncodeDecodeUTF8:
    def __init__(self):
        pass

    @staticmethod
    def decode_value(value):
        """
        Decodes a value from bytes to a string if it's not None.
        """
        return value.decode("utf-8") if value is not None else None

    @staticmethod
    def encode_value(value):
        """
        Encodes a value to bytes if it's a string.
        """
        if isinstance(value, str):
            return value.encode("utf-8")
        return value

    @staticmethod
    def decode_hash(hash_data, exempt_keys=None):
        """
        Decodes all fields and values in a hash.
        Certain keys are exempt from decoding and returned as raw bytes.
        """
        exempt_keys = exempt_keys or set()

        decoded_data = {}
        for key, value in hash_data.items():
            decoded_key = key.decode("utf-8")
            if decoded_key in exempt_keys:
                decoded_data[decoded_key] = value
            else:
                decoded_data[decoded_key] = EncodeDecodeUTF8.decode_value(value)
        return decoded_data
