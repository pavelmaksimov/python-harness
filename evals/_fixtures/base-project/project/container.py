from project.libs.structures import LazyInit


class Services:
    """Registered collaborators; add LazyService entries per component."""


Container = LazyInit(Services)
