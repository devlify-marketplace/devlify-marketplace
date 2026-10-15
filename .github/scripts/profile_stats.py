#!/usr/bin/env python3
"""Generate premium profile stats cards (dark + light SVG) and refresh the recent-repos list.

Runs inside GitHub Actions. Uses only the standard library.
Env: GITHUB_TOKEN (recommended), PROFILE_USER, ASSETS_DIR, README
"""
import colorsys, json, os, re, sys, urllib.request, urllib.error

USER = os.environ.get("PROFILE_USER", "devlify-marketplace")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
ASSETS = os.environ.get("ASSETS_DIR", "assets")
README = os.environ.get("README", "README.md")

SERIF = "'Iowan Old Style','Palatino Linotype',Palatino,'Book Antiqua',Georgia,serif"
SANS = "'Inter','SF Pro Display','Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono','SF Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
ICE, CYAN, VIOLET, LILAC, GOLD, GOLD2, MUTED = "#67e8f9", "#22d3ee", "#8b5cf6", "#c4b5fd", "#e6cf9d", "#c9a96a", "#93a1b8"
RM = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"

LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5", "Java": "#b07219",
    "C++": "#f34b7d", "PHP": "#8892be", "HTML": "#e34c26", "CSS": "#8b5cf6", "Kotlin": "#A97BFF",
    "Solidity": "#8f8f9a", "Shell": "#89e051", "Dockerfile": "#384d54", "C": "#9aa0a6", "Dart": "#00B4AB",
}


def request(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def rest(path):
    return request("https://api.github.com" + path)


def fetch():
    user = rest(f"/users/{USER}")
    repos, page = [], 1
    while True:
        chunk = rest(f"/users/{USER}/repos?per_page=100&type=owner&sort=pushed&page={page}")
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in own)
    forks = sum(r["forks_count"] for r in own)

    langs = {}
    if TOKEN:
        for r in [r for r in own if not r["archived"]][:80]:
            try:
                for k, v in rest(f"/repos/{USER}/{r['name']}/languages").items():
                    langs[k] = langs.get(k, 0) + v
            except Exception:
                pass
    if not langs:  # fallback: weight primary language by repo size
        for r in own:
            if r.get("language"):
                langs[r["language"]] = langs.get(r["language"], 0) + max(r.get("size", 1), 1)

    contrib = None
    if TOKEN:
        q = """query($login:String!){user(login:$login){contributionsCollection{
          totalCommitContributions totalPullRequestContributions totalIssueContributions restrictedContributionsCount}}}"""
        try:
            res = request("https://api.github.com/graphql", {"query": q, "variables": {"login": USER}})
            c = res["data"]["user"]["contributionsCollection"]
            contrib = dict(commits=c["totalCommitContributions"] + c["restrictedContributionsCount"],
                           prs=c["totalPullRequestContributions"], issues=c["totalIssueContributions"])
        except Exception as e:
            print("graphql skipped:", e)
    return user, own, stars, forks, langs, contrib


# ------------------------------------------------------------------ rendering
def fmt(n):
    return f"{n/1000:.1f}k" if n >= 10000 else f"{n:,}"


def shell(W, H, title, sub, body, label):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#070b14"/><stop offset="1" stop-color="#100c25"/></linearGradient>
    <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".18"/><stop offset=".5" stop-color="{GOLD}" stop-opacity=".18"/><stop offset="1" stop-color="{CYAN}" stop-opacity=".2"/></linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{GOLD}"/><stop offset="1" stop-color="{GOLD2}"/></linearGradient>
    <linearGradient id="num" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#b9cdea"/></linearGradient>
    <linearGradient id="bar" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>
    <radialGradient id="glow" cx="1" cy="0" r="1"><stop offset="0" stop-color="{CYAN}" stop-opacity=".18"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>
    <clipPath id="c"><rect width="{W}" height="{H}" rx="22"/></clipPath>
  </defs>
  <style>
    .in{{animation:in .8s cubic-bezier(.2,.7,.2,1) backwards}} @keyframes in{{from{{opacity:0;transform:translateY(8px)}}}}
    .grow{{transform-box:fill-box;transform-origin:left;animation:grow 1.2s cubic-bezier(.2,.7,.2,1) backwards}} @keyframes grow{{from{{transform:scaleX(0)}}}}
    {RM}
  </style>
  <g clip-path="url(#c)"><rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#glow)"/></g>
  <rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="21.25" fill="none" stroke="url(#edge)" stroke-width="1.5"/>
  <path d="M30 .75 H{W-30}" stroke="{GOLD}" stroke-opacity=".3"/>
  <text x="24" y="42" font-family="{SERIF}" font-size="23" font-weight="600" fill="#f4f6fb">{title}</text>
  <text x="24" y="60" font-family="{SANS}" font-size="12.5" fill="#64748b">{sub}</text>
  {body}
</svg>
'''


def stats_svg(user, stars, forks, contrib):
    items = [("Repositories", user["public_repos"]), ("Stars earned", stars), ("Forks", forks), ("Followers", user["followers"])]
    if contrib:
        items += [("Commits, past year", contrib["commits"]), ("Pull requests", contrib["prs"])]
    W, cols = 440, 3
    rows = (len(items) + cols - 1) // cols
    H = 84 + rows * 62 + 22
    body = ""
    for i, (label, val) in enumerate(items):
        r, c = divmod(i, cols)
        x, y = 24 + c * 134, 112 + r * 62
        body += (f'<g class="in" style="animation-delay:{.1+i*.1:.1f}s"><text x="{x}" y="{y}" font-family="{SERIF}" font-size="30" font-weight="600" fill="url(#num)">{fmt(val)}</text>'
                 f'<text x="{x}" y="{y+20}" font-family="{SANS}" font-size="12" fill="{MUTED}">{label}</text></g>')
    return shell(W, H, "GitHub activity", USER, body, f"GitHub statistics for {USER}")


def langs_svg(langs):
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    W, H = 440, 84 + len(top) * 30 + 14
    body = ""
    for i, (name, v) in enumerate(top):
        pct = v / total * 100
        y = 92 + i * 30
        col = LANG_COLORS.get(name, ICE)
        bw = max(6, 196 * pct / (top[0][1] / total * 100))
        body += (f'<g class="in" style="animation-delay:{.1+i*.08:.2f}s"><circle cx="30" cy="{y+4}" r="4.5" fill="{col}"/>'
                 f'<text x="44" y="{y+9}" font-family="{SANS}" font-size="13.5" fill="#cbd5e6">{name}</text>'
                 f'<rect x="172" y="{y}" width="196" height="9" rx="4.5" fill="#16213a"/>'
                 f'<rect class="grow" x="172" y="{y}" width="{bw:.1f}" height="9" rx="4.5" fill="url(#bar)" style="animation-delay:{.3+i*.1:.1f}s"/>'
                 f'<text x="{W-24}" y="{y+9}" text-anchor="end" font-family="{MONO}" font-size="12" fill="{MUTED}">{pct:.1f}%</text></g>')
    return shell(W, H, "Top languages", "by code volume", body, f"Top languages for {USER}")


_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def _map(m):
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    l2 = 0.07 + 0.88 * (1 - l) if (s < 0.55 or l < 0.28 or l > 0.78) else l * 0.6
    r2, g2, b2 = colorsys.hls_to_rgb(hh, l2, s)
    return "#%02x%02x%02x" % (round(r2 * 255), round(g2 * 255), round(b2 * 255))


def write_pair(name, svg):
    os.makedirs(ASSETS, exist_ok=True)
    with open(os.path.join(ASSETS, name + ".svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    with open(os.path.join(ASSETS, name + "-light.svg"), "w", encoding="utf-8") as f:
        f.write(_HEX.sub(_map, svg))
    print("wrote", name)


def update_readme(repos):
    if not os.path.exists(README):
        return
    skip = {USER.lower(), ".github"}
    recent = [r for r in repos if r["name"].lower() not in skip and not r["archived"]][:5]
    lines = []
    for r in recent:
        desc = (r.get("description") or "").strip().replace("|", "/")
        lang = f" `{r['language']}`" if r.get("language") else ""
        lines.append(f"- [**{r['name']}**]({r['html_url']}){lang}" + (f": {desc}" if desc else ""))
    block = "<!-- RECENT:START -->\n" + "\n".join(lines) + "\n<!-- RECENT:END -->"
    txt = open(README, encoding="utf-8").read()
    new = re.sub(r"<!-- RECENT:START -->.*?<!-- RECENT:END -->", lambda m: block, txt, flags=re.S)
    if new != txt:
        open(README, "w", encoding="utf-8").write(new)
        print("README recent repos updated")


def main():
    try:
        user, own, stars, forks, langs, contrib = fetch()
    except urllib.error.HTTPError as e:
        print("GitHub API error:", e)
        sys.exit(1)
    write_pair("stats", stats_svg(user, stars, forks, contrib))
    if langs:
        write_pair("langs", langs_svg(langs))
    update_readme(own)


if __name__ == "__main__":
    main()
