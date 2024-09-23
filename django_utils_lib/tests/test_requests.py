from django_utils_lib.requests import object_to_multipart_dict


def test_object_to_multipart_dict():
    regular_dict = {
        "a": 1,
        "b": ("tuple_a", "tuple_b"),
        "c": ["list_a", "list_b"],
        "nested_dict": {"nested_a_b": {"d": "d test"}, "e": "e test", "f": 24.1},
        "nested_objs_list": [{"name": "nested obj a"}, {"name": "nested obj b"}],
    }
    multipart_dict = object_to_multipart_dict(regular_dict)
    assert multipart_dict.get("a") == 1
    assert multipart_dict.get("b[0]") == "tuple_a"
    assert multipart_dict.get("b[1]") == "tuple_b"
    assert multipart_dict.get("c[0]") == "list_a"
    assert multipart_dict.get("c[1]") == "list_b"
    assert multipart_dict.get("nested_dict[nested_a_b][d]") == "d test"
    assert multipart_dict.get("nested_dict[e]") == "e test"
    assert multipart_dict.get("nested_dict[f]") == 24.1
    assert multipart_dict.get("nested_objs_list[0][name]") == "nested obj a"
    assert multipart_dict.get("nested_objs_list[1][name]") == "nested obj b"
