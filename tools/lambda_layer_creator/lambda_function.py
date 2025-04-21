import sys
import subprocess
import os
import shutil
import importlib
import platform
import boto3  # <--- Import boto3 early
from botocore.exceptions import ClientError
import traceback

# --- 설정 ---
PACKAGE_NAME = "semver"
INSTALL_DIR = "/tmp/python"
ZIP_FILENAME_BASE = f"{PACKAGE_NAME}_layer"
ZIP_FILENAME = f"{ZIP_FILENAME_BASE}.zip"
ZIP_FILEPATH_TMP = f"/tmp/{ZIP_FILENAME}"
S3_BUCKET_NAME = "slack-chatbot-layer-storage"
S3_KEY = f"lambda-layers/{ZIP_FILENAME}"

# --- sys.path 설정 ---
# 주의: 이 시점 이후에 import 되는 모듈은 /tmp/python을 우선 검색할 수 있음
# 하지만 boto3는 이미 위에서 import 되었으므로, 내장 버전이 로드될 가능성이 높음.
if INSTALL_DIR not in sys.path:
    sys.path.insert(0, INSTALL_DIR)

print(f"Initial sys.path: {sys.path}")

# !!! 중요: S3 클라이언트를 핸들러 초기에, 내장 boto3를 사용하여 생성 !!!
# 이렇게 하면 /tmp/python에 설치된 버전과의 충돌을 피할 수 있음.
try:
    s3_client_global = boto3.client("s3")
    print("Successfully created S3 client using system boto3.")
except Exception as e:
    print(f"CRITICAL: Failed to create initial S3 client: {e}")
    # S3 클라이언트 생성 실패 시, 이후 업로드 불가하므로 핸들러에서 처리 필요
    s3_client_global = None

# --- 함수 정의 ---


def install_package(package_name, target_dir):
    """지정된 디렉토리에 Python 패키지를 설치합니다 (Warm start 고려)."""
    # ... (이 함수 내용은 이전과 동일) ...
    # try:
    #     # 설치 전에 import 시도 (Warm start 최적화)
    #     importlib.import_module('langchain_aws.chat_models') # 특정 모듈 확인
    #     print(f"'{package_name}' 패키지는 이미 import 가능합니다. 설치를 건너<0xEB><0x9A><0x8D>니다.")
    #     return True
    # except ImportError:
    #     print(f"'{package_name}' import 불가. 설치를 진행합니다...")

    # 이전 실행에서 남은 디렉토리가 있다면 삭제 (깨끗한 상태에서 시작)
    if os.path.exists(target_dir):
        print(f"기존 설치 디렉토리 '{target_dir}' 삭제 중...")
        try:
            shutil.rmtree(target_dir)
        except Exception as e:
            print(f"기존 디렉토리 삭제 중 오류: {e}")

    os.makedirs(target_dir, exist_ok=True)
    print(f"설치 대상 디렉토리: '{target_dir}'")

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        package_name,
        "--target",
        target_dir,
        "--no-cache-dir",
        "--upgrade",
    ]
    print(f"실행 명령: {' '.join(command)}")
    try:
        process = subprocess.run(
            command, check=True, capture_output=True, text=True, encoding="utf-8"
        )
        print(f"'{package_name}' 설치 명령 완료.")
        print("Pip stdout (last 500 chars):", process.stdout[-500:])
        if process.stderr:
            print("Pip stderr:", process.stderr)

        print(f"설치 후 {target_dir} 내용 확인 중...")
        if os.path.exists(target_dir):
            print(
                f"Contents of {target_dir} (first few): {os.listdir(target_dir)[:10]}"
            )
        else:
            print(f"오류: 설치 후 '{target_dir}' 디렉토리가 존재하지 않습니다!")
            return False

        print("Importlib 캐시를 무효화합니다...")
        importlib.invalidate_caches()

        print("캐시 무효화 후 import 재시도...")
        try:
            importlib.import_module("pipgrip")
            print("설치 및 캐시 무효화 후 import 성공!")
            return True
        except ImportError as e_import:
            print(f"캐시 무효화 후에도 import 실패: {e_import}")
            print(f"최종 sys.path 확인: {sys.path}")
            return False

    except subprocess.CalledProcessError as e:
        print(f"패키지 설치 중 오류 발생 (CalledProcessError): {e}")
        print("오류 출력 (stdout):", e.stdout)
        print("오류 출력 (stderr):", e.stderr)
        return False
    except Exception as e:
        print(f"패키지 설치 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()
        return False


def create_zip_archive(source_dir_name, archive_fullpath_no_ext):
    """지정된 이름의 디렉토리를 Lambda Layer 구조로 압축합니다."""
    # ... (이 함수 내용은 이전과 동일) ...
    source_dir_fullpath = f"/tmp/{source_dir_name}"
    print(
        f"'{source_dir_fullpath}' 디렉토리를 '{archive_fullpath_no_ext}.zip' 파일로 압축합니다 (Lambda Layer 구조)..."
    )

    if not os.path.isdir(source_dir_fullpath):
        print(f"오류: 압축할 소스 디렉토리 '{source_dir_fullpath}'를 찾을 수 없습니다.")
        return None

    try:
        shutil.make_archive(
            base_name=archive_fullpath_no_ext,
            format="zip",
            root_dir="/tmp",
            base_dir=source_dir_name,
        )

        zip_filepath = f"{archive_fullpath_no_ext}.zip"
        if os.path.exists(zip_filepath):
            print(f"'{zip_filepath}' 압축 파일 생성 완료 (Lambda Layer 구조).")
            file_size = os.path.getsize(zip_filepath)
            print(f"압축 파일 크기: {file_size / (1024*1024):.2f} MB")
            return zip_filepath
        else:
            print(
                f"오류: shutil.make_archive 실행 후 '{zip_filepath}' 파일이 존재하지 않습니다."
            )
            return None
    except Exception as e:
        print(f"압축 파일 생성 중 오류 발생: {e}")
        traceback.print_exc()
        return None


# upload_to_s3 함수가 미리 생성된 S3 클라이언트를 받도록 수정
def upload_to_s3(s3_client, file_name, bucket, object_name=None):
    """파일을 S3 버킷에 업로드합니다 (미리 생성된 클라이언트 사용)."""
    if not s3_client:
        print("오류: S3 클라이언트가 초기화되지 않아 업로드할 수 없습니다.")
        return False

    if object_name is None:
        object_name = os.path.basename(file_name)

    print(
        f"'{file_name}' 파일을 S3 버킷 '{bucket}'에 '{object_name}'으로 업로드합니다..."
    )
    # s3_client = boto3.client('s3') # <--- 여기서 생성하지 않음
    try:
        s3_client.upload_file(
            file_name,
            bucket,
            object_name,
            ExtraArgs={"ACL": "bucket-owner-full-control"},
        )
        print("S3 업로드 완료.")
        return True
    except ClientError as e:
        print(f"S3 업로드 중 오류 발생: {e}")
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "AccessDenied":
            print(
                "권한 오류: Lambda 실행 역할에 S3 PutObject 권한이 있는지 확인하세요."
            )
        elif error_code == "NoSuchBucket":
            print(
                f"버킷 오류: S3 버킷 '{bucket}'이(가) 존재하지 않거나 접근할 수 없습니다."
            )
        # 다른 ClientError 코드 처리 추가 가능
        return False
    except FileNotFoundError:
        print(f"오류: 업로드할 파일 '{file_name}'을 찾을 수 없습니다.")
        return False
    except Exception as e:
        print(f"S3 업로드 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()
        return False


def cleanup(paths_to_remove):
    """임시 디렉토리와 파일을 삭제합니다."""
    # ... (이 함수 내용은 이전과 동일) ...
    print(f"임시 파일 및 디렉토리 정리 시도: {paths_to_remove}")
    for path in paths_to_remove:
        if not path:
            continue
        try:
            if os.path.isfile(path):
                os.remove(path)
                print(f"파일 '{path}' 삭제 완료.")
            elif os.path.isdir(path):
                shutil.rmtree(path)
                print(f"디렉토리 '{path}' 삭제 완료.")
        except FileNotFoundError:
            print(f"정리 대상 '{path}'를 찾을 수 없어 건너<0xEB><0x9A><0x8D>니다.")
        except Exception as e:
            print(f"경로 '{path}' 정리 중 오류 발생: {e}")


# --- Lambda 핸들러 ---


def lambda_handler(event, context):
    print(f"Lambda 함수 시작. Request ID: {context.aws_request_id}")

    # !!! S3 클라이언트가 초기에 성공적으로 생성되었는지 확인 !!!
    if not s3_client_global:
        print("치명적 오류: S3 클라이언트를 초기화할 수 없어 함수 실행을 중단합니다.")
        return {"statusCode": 500, "body": "S3 클라이언트 초기화 실패"}

    installed_successfully = False
    zip_filepath = None
    uploaded_successfully = False
    paths_to_clean = []

    try:
        # 1. langchain-aws 패키지 설치 시도
        installed_successfully = install_package(PACKAGE_NAME, INSTALL_DIR)
        if not installed_successfully:
            print("패키지 설치 최종 실패.")
            if os.path.exists(INSTALL_DIR):
                paths_to_clean.append(INSTALL_DIR)
            return {
                "statusCode": 500,
                "body": f"'{PACKAGE_NAME}' 패키지 설치 실패 (import 불가)",
            }
        paths_to_clean.append(INSTALL_DIR)

        # --- 설치된 패키지 사용 확인 (선택적) ---
        # try:
        #     from langchain_aws.chat_models import ChatBedrock
        #     print("메인 로직에서 langchain_aws import 확인 성공.")
        # except ImportError as e:
        #      print(f"경고: 설치 성공 후에도 메인 로직 import 실패?: {e}")
        # except Exception as e:
        #      print(f"경고: 설치된 패키지 사용 확인 중 오류: {e}")

        # 2. 설치된 패키지 압축 (Lambda Layer 형식)
        install_dir_name = os.path.basename(INSTALL_DIR)  # "python"
        archive_base = ZIP_FILEPATH_TMP.replace(".zip", "")
        zip_filepath = create_zip_archive(install_dir_name, archive_base)

        if not zip_filepath or not os.path.exists(zip_filepath):
            print("Zip 파일 생성 실패.")
            paths_to_clean.append(ZIP_FILEPATH_TMP)  # 실패한 zip 파일 경로도 정리 시도
            return {"statusCode": 500, "body": "압축 파일 생성 실패"}
        paths_to_clean.append(zip_filepath)

        # 3. S3에 업로드 (미리 생성한 s3_client_global 사용)
        uploaded_successfully = upload_to_s3(
            s3_client_global, zip_filepath, S3_BUCKET_NAME, S3_KEY
        )
        if not uploaded_successfully:
            print("S3 업로드 실패.")
            return {"statusCode": 500, "body": "S3 업로드 실패"}

        # 4. 모든 과정 성공 시 완료 메시지 반환
        print("패키지 설치, 압축, S3 업로드 모두 성공!")
        return {
            "statusCode": 200,
            "body": f"Lambda Layer 패키지 '{ZIP_FILENAME}' 생성 및 S3 버킷 '{S3_BUCKET_NAME}'의 '{S3_KEY}' 경로에 업로드 완료!",
        }

    except Exception as e:
        print(f"Lambda 핸들러 실행 중 예외 발생: {e}")
        traceback.print_exc()
        return {"statusCode": 500, "body": f"Lambda 실행 중 예상치 못한 오류: {e}"}

    finally:
        # 5. 임시 파일/디렉토리 정리
        print("정리 단계 시작...")
        cleanup(paths_to_clean)
        print(f"Lambda 함수 종료. Request ID: {context.aws_request_id}")
