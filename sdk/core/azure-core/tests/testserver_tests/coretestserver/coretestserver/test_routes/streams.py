# coding: utf-8
# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See LICENSE.txt in the project root for
# license information.
# -------------------------------------------------------------------------
import os
import gzip
import tempfile
from flask import (
    Response,
    Blueprint,
)

streams_api = Blueprint("streams_api", __name__)

# Mock for the live https://coretests.blob.core.windows.net/tests/* fixtures
# (the source blob is no longer publicly reachable). Mounted at /tests by the
# Flask app so the URL-rewrite fixture in conftest.py can route the original
# coretests.blob.core.windows.net URLs here.
blob_tests_api = Blueprint("blob_tests_api", __name__)


class StreamingBody:
    def __iter__(self):
        yield b"Hello, "
        yield b"world!"


def streaming_body():
    yield b"Hello, "
    yield b"world!"


def stream_json_error():
    yield '{"error": {"code": "BadRequest", '
    yield ' "message": "You made a bad request"}}'


def streaming_test():
    yield b"test"


def stream_compressed_header_error():
    yield b"test"


def stream_compressed_no_header():
    with gzip.open("test.tar.gz", "wb") as f:
        f.write(b"test")

    with open(os.path.join(os.path.abspath("test.tar.gz")), "rb") as fd:
        yield fd.read()

    os.remove("test.tar.gz")


@streams_api.route("/basic", methods=["GET"])
def basic():
    return Response(streaming_body(), status=200)


@streams_api.route("/iterable", methods=["GET"])
def iterable():
    return Response(StreamingBody(), status=200)


@streams_api.route("/error", methods=["GET"])
def error():
    return Response(stream_json_error(), status=400)


@streams_api.route("/string", methods=["GET"])
def string():
    return Response(streaming_test(), status=200, mimetype="text/plain")


@streams_api.route("/compressed_no_header", methods=["GET"])
def compressed_no_header():
    return Response(stream_compressed_no_header(), status=300)


@streams_api.route("/compressed", methods=["GET"])
def compressed():
    return Response(stream_compressed_header_error(), status=300, headers={"Content-Encoding": "gzip"})


def compressed_stream():
    with tempfile.TemporaryFile(mode="w+b") as f:
        gzf = gzip.GzipFile(mode="w+b", fileobj=f)
        gzf.write(b"test")
        gzf.flush()
        f.seek(0)
        yield f.read()


@streams_api.route("/decompress_header", methods=["GET"])
def decompress_header():
    return Response(compressed_stream(), status=200, headers={"Content-Encoding": "gzip"})


# --- Mock of https://coretests.blob.core.windows.net/tests/* ---

# Hardcoded gzip-of-b"test" (mtime=0, OS=TOPS-20 / 0x0a). Matches the literal
# byte sequence asserted by test_rest_stream_responses.test_decompress_compressed_no_header,
# which was originally captured against a specific server-side encoding.
# Python's default gzip.GzipFile picks current mtime + Unix OS byte, so a
# locally-generated payload would not match.
_GZIPPED_TEST_BYTES = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\n+I-.\x01\x00\x0c~\x7f\xd8\x04\x00\x00\x00"


@blob_tests_api.route("/test.txt", methods=["GET"])
def blob_test_txt():
    return Response(b"test", status=200, mimetype="text/plain")


@blob_tests_api.route("/test.tar.gz", methods=["GET"])
def blob_test_tar_gz():
    # Gzipped bytes WITHOUT Content-Encoding header — client receives raw gzipped payload.
    return Response(_GZIPPED_TEST_BYTES, status=200, mimetype="application/octet-stream")


@blob_tests_api.route("/test_with_header.tar.gz", methods=["GET"])
def blob_test_with_header_tar_gz():
    # Gzipped bytes WITH Content-Encoding: gzip — client transparently decompresses.
    return Response(_GZIPPED_TEST_BYTES, status=200, headers={"Content-Encoding": "gzip"})


@blob_tests_api.route("/test_with_header.txt", methods=["GET"])
def blob_test_with_header_txt():
    # Malformed: PLAIN body but advertised as Content-Encoding: gzip. Tests
    # verify the client raises DecodeError when asked to decompress, and
    # returns the raw plain bytes when decompress=False.
    return Response(b"test", status=200, headers={"Content-Encoding": "gzip"})
