NAV = {
    "CITIZEN": [
        ("Dashboard", "/dashboard/", "layout-dashboard"),
        ("Report issue", "/issues/new/", "file-plus"),
        ("My reports", "/issues/mine/", "clipboard-list"),
        ("Community", "/issues/", "list"),
        ("Map", "/map/", "map"),
    ],
    "STAFF": [
        ("My tasks", "/tasks/", "clipboard-list"),
        ("Map", "/map/", "map"),
    ],
    "ADMIN": [
        ("Overview", "/admin-panel/", "bar-chart-3"),
        ("All issues", "/issues/", "list"),
        ("Map", "/map/", "map"),
        ("Staff", "/admin-panel/staff/", "users"),
    ],
}
COMMON = [("Notifications", "/notifications/", "bell"), ("Profile", "/profile/", "user")]


def navigation(request):
    """Sidebar links for the signed-in user's role. Display only: views enforce access."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"nav_items": []}
    path = request.path
    return {
        "nav_items": [
            {"label": label, "url": url, "icon": ic, "active": path == url}
            for label, url, ic in NAV.get(user.role, []) + COMMON
        ],
        "unread_count": user.notifications.filter(read_at__isnull=True).count(),
    }
