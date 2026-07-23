"""MSR image error hierarchy with HTTP status + machine code.

Routes translate these to JSON error responses. Home mock never raises the
office-source variants; office adapter never falls back to mock bytes.
"""


class MsrImageError(Exception):
    status = 500
    code = "msr_image_error"


class InvalidToolIp(MsrImageError):
    status = 400
    code = "invalid_tool_ip"


class ConfigError(MsrImageError):
    status = 500
    code = "office_configuration_error"


class SourceUnavailable(MsrImageError):
    status = 503
    code = "office_source_unavailable"


class ImageNotFound(MsrImageError):
    status = 404
    code = "image_not_found"
