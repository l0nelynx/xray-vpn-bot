(() => {
  const FALLBACK = { pulls: 2198, stars: 0 };

  function formatCount(n) {
    if (n == null || Number.isNaN(n)) return "—";
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(n >= 10_000 ? 0 : 1)}K`;
    return String(n);
  }

  function setStat(key, value) {
    const el = document.querySelector(`[data-stat="${key}"]`);
    if (el) el.textContent = formatCount(value);
  }

  async function load() {
    setStat("docker-pulls", FALLBACK.pulls);
    setStat("github-stars", FALLBACK.stars);

    const [hub, gh] = await Promise.allSettled([
      fetch("https://hub.docker.com/v2/repositories/spicycheeze/dashboard/").then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      }),
      fetch("https://api.github.com/repos/l0nelynx/xray-vpn-bot").then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      }),
    ]);

    if (hub.status === "fulfilled" && typeof hub.value.pull_count === "number") {
      setStat("docker-pulls", hub.value.pull_count);
    }
    if (gh.status === "fulfilled" && typeof gh.value.stargazers_count === "number") {
      setStat("github-stars", gh.value.stargazers_count);
    }
  }

  load();
})();
