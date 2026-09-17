import typing as t

UserIdT = t.NewType("UserIdT", t.Annotated[int, "User ID"])
