"""
Thin wrappers around the dataset's supplied ZentroMart tools.

Keep the original tools as the source of truth for order lookup and ticket creation.
The provided lookup_order is expected to enforce caller verification.
"""

import importlib
import inspect
import sys
from pathlib import Path

# Add the extracted dataset root to Python's import path.
DATASET_ROOT = Path("dataset")
if str(DATASET_ROOT.resolve()) not in sys.path:
    sys.path.insert(0, str(DATASET_ROOT.resolve()))


def _load_original_tools():
    """
    Supports either:
      dataset/tools/tools.py
      tools/tools.py (if the dataset itself is the project root)
    """
    try:
        module = importlib.import_module("tools.tools")
        if hasattr(module, "lookup_order") and hasattr(module, "create_ticket"):
            return module
    except ImportError:
        pass

    raise ImportError(
        "Could not import lookup_order/create_ticket. Check that the supplied "
        "dataset's tools/tools.py is available and that its folder is on PYTHONPATH."
    )


_original_tools = _load_original_tools()


def lookup_order(order_id, verification=None, verification_value=None):
    """
    Look up an order using the provided dataset tool.

    Accepts verification via either `verification` or `verification_value`
    (positional or keyword argument) to maintain broad compatibility.
    Passes the verification value using the target parameter name accepted
    by the dataset tool (verification_value).
    """
    value = verification_value if verification_value is not None else verification
    function = _original_tools.lookup_order
    parameters = inspect.signature(function).parameters

    if value is not None:
        for candidate in ("verification_value", "verification", "phone_last4", "delivery_pincode", "phone_last_four"):
            if candidate in parameters:
                return function(order_id, **{candidate: value})

    return function(order_id)


def create_ticket(summary, order_id=None, reason=None, intent=None):
    """Create a support ticket using the supplied tool; return its result unchanged."""
    return _original_tools.create_ticket(
        summary,
        order_id=order_id,
        reason=reason,
        intent=intent,
    )


if __name__ == "__main__":
    import inspect
    print("lookup_order signature:", inspect.signature(_original_tools.lookup_order))
    print("create_ticket signature:", inspect.signature(_original_tools.create_ticket))
    print("Imported the supplied ZentroMart tools successfully.")
