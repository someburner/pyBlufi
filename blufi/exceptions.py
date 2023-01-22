class BluetoothError(Exception):
    """Catch-all exception for Bluetooth related errors."""

class ConnectionError(BluetoothError):  # pylint: disable=redefined-builtin
    """Raised when a connection is unavailable."""

class RoleError(BluetoothError):
    """Raised when a resource is used as the mismatched role. For example, if a local CCCD is
    attempted to be set but it can only be set when remote."""

class SecurityError(BluetoothError):
    """Raised when a security related error occurs."""
