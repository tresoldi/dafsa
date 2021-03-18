"""
Common functions of the library.
"""

# Import Python standard libraries
import re
from contextlib import closing

# Import from local modules
from .exceptions import InvalidWildCardExpressionError

# A '?' followed by an '*' in the wildcard expr is illegal
_RE_ASTERISK_QUESTION = re.compile(r"\?+(?=\*+)")

# Any special character apart from '*' or '?' is illegal.
_RE_ILLEGAL_CHARS = re.compile(r"[^\w?*]+")


def validate_expression(expression: str) -> str:
    """
    Validate and shorten a wildcard expression.

    The wildcard expression is validated and, if needed, shortened without
    changing the intended meaning. An `InvalidWildCardExpressionError`
    exception is raised if the expression cannot be validated.

    :param expression: The wildcard expression to be validated.
    :return: A shortened copy of the wildcard expression.
    """

    try:
        if re.search(_RE_ASTERISK_QUESTION, expression) is not None:
            raise InvalidWildCardExpressionError(
                expression,
                "A '?' followed by an '*' in the wildcard expr is illegal.",
            )

        if re.search(_RE_ILLEGAL_CHARS, expression) is not None:
            raise InvalidWildCardExpressionError(
                expression, "Illegal characters in expression."
            )

    except InvalidWildCardExpressionError as e:
        raise e

    # Replace consecutive * with single *
    result = re.sub(r"\*+", "*", expression)

    # Replace consecutive ? with a single ?
    result = re.sub(r"\?+", "?", result)

    # Replace consecutive '*?' with a single group '*'
    result = re.sub(r"(\*\?)+", "*", result)

    return result


# TODO: only used in `FSA`, drop it when possible
def gen_source(source):
    if hasattr(source, "read"):
        input_file = source
    else:
        input_file = open(source, "r")

    with closing(input_file):
        for line in input_file:
            yield line.strip()
