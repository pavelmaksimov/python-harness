import typing as t

UserIdT = t.NewType("UserIdT", t.Annotated[int, "User ID"])
OrderIdT = t.NewType("OrderIdT", t.Annotated[int, "Order ID"])
