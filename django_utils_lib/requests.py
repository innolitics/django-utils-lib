from typing import Dict, Optional


def object_to_multipart_dict(obj: Dict, existing_multipart_dict: Optional[dict] = None, key_prefix="") -> Dict:
    """
    This is basically the inverse of a multi-part form parser, which can additionally
    handle nested entries.

    The main use-case for this is constructing requests in Python that emulate
    a multipart FormData payload that would normally be sent by the frontend.

    Nested entries get flattened / hoisted, so that the final dict is a flat
    key-value map, with bracket notation used for nested entries. List items are
    also hoisted up, with indices put within leading brackets.

    Warning: values are not stringified (but would be in a true multipart payload)

    @example
    ```
    nested_dict = {"a": 1, "multi": [{"id": "abc"}, {"id": "123"}]}
    print(object_to_multipart_dict(nested_dict))
    # > {'a': 1, 'multi[0][id]': 'abc', 'multi[1][id]': '123'}
    ```
    """
    result = existing_multipart_dict or {}
    for _key, val in obj.items():
        # If this is a nested child, we need to wrap key in brackets
        _key = f"[{_key}]" if existing_multipart_dict else _key
        key = key_prefix + _key
        if isinstance(val, dict):
            object_to_multipart_dict(val, result, key)
        elif isinstance(val, (list, tuple)):
            for i, sub_val in enumerate(val):
                sub_key = f"{key}[{i}]"
                if isinstance(sub_val, dict):
                    object_to_multipart_dict(sub_val, result, sub_key)
                else:
                    result[sub_key] = sub_val
        else:
            result[key] = val
    return result
