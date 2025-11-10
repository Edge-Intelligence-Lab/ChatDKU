import os
from typing import IO, Optional, Any
from unstructured.file_utils.encoding import format_encoding_str
from unstructured.logger import logger
from unstructured.file_utils.filetype import (
    FileType,
    STR_TO_FILETYPE,
    EXT_TO_FILETYPE,
    TXT_MIME_TYPES,
    PLAIN_TEXT_EXTENSIONS,
    LIBMAGIC_AVAILABLE,
    _resolve_symlink,
    _is_text_file_a_json,
    _is_text_file_a_csv,
    _is_code_mime_type,
    _check_eml_from_buffer,
    _detect_filetype_from_octet_stream,
)


def exactly_one(**kwargs: Any) -> None:
    """
    Verify arguments; exactly one of all keyword arguments must not be None.

    Example:
        >>> exactly_one(filename=filename, file=file, text=text, url=url)
    """
    if sum([(arg is not None and arg != "") for arg in kwargs.values()]) != 1:
        names = list(kwargs.keys())
        if len(names) > 1:
            message = f"Exactly one of {', '.join(names[:-1])} and {names[-1]} must be specified."
        else:
            message = f"{names[0]} must be specified."
        raise ValueError(message)


def custom_detect_filetype(
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    file: Optional[IO[bytes]] = None,
    file_filename: Optional[str] = None,
    encoding: Optional[str] = "utf-8",
) -> Optional[FileType]:
    """Use libmagic to determine a file's type. Helps determine which partition brick
    to use for a given file. A return value of None indicates a non-supported file type.
    """
    mime_type = None
    exactly_one(filename=filename, file=file)

    # first check (content_type)
    if content_type:
        filetype = STR_TO_FILETYPE.get(content_type)
        if filetype:
            return filetype

    # second check (filename/file_name/file)
    # continue if successfully define mime_type
    if filename or file_filename:
        _filename = filename or file_filename or ""
        _, extension = os.path.splitext(_filename)
        extension = extension.lower()
        if os.path.isfile(_filename) and LIBMAGIC_AVAILABLE:
            import magic

            mime_type = magic.from_file(
                _resolve_symlink(filename or file_filename),
                mime=True,
            )  # type: ignore
        elif os.path.isfile(_filename):
            import filetype as ft

            mime_type = ft.guess_mime(filename)
        if (
            extension == ".htm"
            or extension == ".html"
            or (mime_type and "html" in mime_type)
        ):
            mime_type = "text/html"
        if mime_type is None:
            return EXT_TO_FILETYPE.get(extension, FileType.UNK)

    elif file is not None:
        if hasattr(file, "name"):
            _, extension = os.path.splitext(file.name)
        else:
            extension = ""
        extension = extension.lower()
        # NOTE(robinson) - the python-magic docs recommend reading at least the first 2048 bytes
        # Increased to 4096 because otherwise .xlsx files get detected as a zip file
        # ref: https://github.com/ahupp/python-magic#usage
        if LIBMAGIC_AVAILABLE:
            mime_type = magic.from_buffer(file.read(4096), mime=True)
        else:
            import filetype as ft

            mime_type = ft.guess_mime(file.read(4096))
        if mime_type is None:
            logger.warning(
                "libmagic is unavailable but assists in filetype detection on file-like objects. "
                "Please consider installing libmagic for better results.",
            )
            return EXT_TO_FILETYPE.get(extension, FileType.UNK)

    else:
        raise ValueError("No filename, file, nor file_filename were specified.")

    """Mime type special cases."""
    # third check (mime_type)

    # NOTE(Crag): older magic lib does not differentiate between xls and doc
    if mime_type == "application/msword" and extension == ".xls":
        return FileType.XLS

    elif mime_type.endswith("xml"):
        if extension == ".html" or extension == ".htm":
            return FileType.HTML
        else:
            return FileType.XML

    elif mime_type in TXT_MIME_TYPES or mime_type.startswith("text"):
        if not encoding:
            encoding = "utf-8"
        formatted_encoding = format_encoding_str(encoding)

        if extension in [
            ".eml",
            ".p7s",
            ".md",
            ".rtf",
            ".html",
            ".rst",
            ".org",
            ".csv",
            ".tsv",
            ".json",
        ]:
            return EXT_TO_FILETYPE.get(extension)

        # NOTE(crag): for older versions of the OS libmagic package, such as is currently
        # installed on the Unstructured docker image, .json files resolve to "text/plain"
        # rather than "application/json". this corrects for that case.
        if _is_text_file_a_json(
            file=file,
            filename=filename,
            encoding=formatted_encoding,
        ):
            return FileType.JSON

        if _is_text_file_a_csv(
            file=file,
            filename=filename,
            encoding=formatted_encoding,
        ):
            return FileType.CSV

        if file and _check_eml_from_buffer(file=file) is True:
            return FileType.EML

        if extension in PLAIN_TEXT_EXTENSIONS:
            return EXT_TO_FILETYPE.get(extension, FileType.UNK)

        # Safety catch
        if mime_type in STR_TO_FILETYPE:
            return STR_TO_FILETYPE[mime_type]

        return FileType.TXT

    elif mime_type == "application/octet-stream":
        if extension == ".docx":
            return FileType.DOCX
        elif file:
            return _detect_filetype_from_octet_stream(file=file)
        else:
            return EXT_TO_FILETYPE.get(extension, FileType.UNK)

    elif mime_type == "application/zip":
        filetype = FileType.UNK
        if file:
            filetype = _detect_filetype_from_octet_stream(file=file)
        elif filename is not None:
            with open(filename, "rb") as f:
                filetype = _detect_filetype_from_octet_stream(file=f)

        extension = extension if extension else ""
        if filetype == FileType.UNK:
            return FileType.ZIP
        else:
            return EXT_TO_FILETYPE.get(extension, filetype)

    elif _is_code_mime_type(mime_type):
        # NOTE(robinson) - we'll treat all code files as plain text for now.
        # we can update this logic and add filetypes for specific languages
        # later if needed.
        return FileType.TXT

    elif mime_type.endswith("empty"):
        return FileType.EMPTY

    # For everything else
    elif mime_type in STR_TO_FILETYPE:
        return STR_TO_FILETYPE[mime_type]

    logger.warning(
        f"The MIME type{f' of {filename!r}' if filename else ''} is {mime_type!r}. "
        "This file type is not currently supported in unstructured.",
    )
    return EXT_TO_FILETYPE.get(extension, FileType.UNK)
