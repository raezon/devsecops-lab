#!/usr/bin/env python3
"""
Quality Gate — vérifie les seuils de sécurité de tous les outils.
Génère security-summary.txt et retourne exit code 1 si bloqué.
"""
import json, sys, os

issues   = []
sections = []


def load(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


# ── Gitleaks ──────────────────────────────────────────────
leaks = load('gitleaks-report.json')
if leaks is not None:
    count  = len(leaks) if isinstance(leaks, list) else 0
    status = "❌ BLOQUÉ" if count > 0 else "✅ OK"
    lines  = []
    for l in (leaks[:5] if isinstance(leaks, list) else []):
        lines.append(f"  • [{l.get('RuleID','?')}] {l.get('File','?')}:{l.get('StartLine','?')} — {l.get('Description','?')}")
    sections.append(f"""🔑 GITLEAKS — Secrets Scanning [{status}]
{'=' * 52}
Secrets détectés : {count}
{chr(10).join(lines) if lines else '  Aucun secret détecté.'}
{'  ⚠️  (5 premiers affichés)' if count > 5 else ''}
Seuil : 0 secret toléré
""")
    if count > 0:
        issues.append(f"GITLEAKS ({count} secret(s))")
else:
    sections.append("🔑 GITLEAKS — rapport introuvable\n")



# ── Trivy ─────────────────────────────────────────────────
trivy = load('trivy-report.json')
if trivy is not None:
    all_vulns = [v for r in trivy.get('Results', [])
                 for v in r.get('Vulnerabilities') or []]
    critical  = sum(v.get('Severity') == 'CRITICAL' for v in all_vulns)
    high      = sum(v.get('Severity') == 'HIGH'     for v in all_vulns)
    status    = "❌ BLOQUÉ" if (critical > 0 or high > 3) else "✅ OK"
    top       = [v for v in all_vulns if v.get('Severity') in ('CRITICAL', 'HIGH')][:5]
    lines     = []
    for v in top:
        lines.append(f"  • [{v.get('Severity')}] {v.get('VulnerabilityID','?')} — "
                     f"{v.get('PkgName','?')} {v.get('InstalledVersion','?')}")
        lines.append(f"    Fix : {v.get('FixedVersion','non disponible')} — "
                     f"{v.get('Title','')[:80]}")
    sections.append(f"""🔬 TRIVY — SCA Image Docker [{status}]
{'=' * 52}
CRITICAL : {critical}   HIGH : {high}
{chr(10).join(lines) if lines else '  Aucune vulnérabilité CRITICAL/HIGH.'}
{'  ⚠️  (5 premières affichées)' if len(top) == 5 else ''}
Seuil : CRITICAL > 0 ou HIGH > 3 = blocage
""")
    if critical > 0 or high > 3:
        issues.append(f"TRIVY (CRITICAL={critical}, HIGH={high})")
else:
    sections.append("🔬 TRIVY — rapport introuvable\n")


# ── ZAP ───────────────────────────────────────────────────
zap = load('zap-report.json')
if zap is not None:
    all_alerts = [a for s in zap.get('site', []) for a in s.get('alerts', [])]
    high       = sum(1 for a in all_alerts if int(a.get('riskcode', 0)) == 3)
    medium     = sum(1 for a in all_alerts if int(a.get('riskcode', 0)) == 2)
    low        = sum(1 for a in all_alerts if int(a.get('riskcode', 0)) == 1)
    status     = "❌ BLOQUÉ" if (high > 0 or medium > 1) else "✅ OK"
    top        = [a for a in all_alerts if int(a.get('riskcode', 0)) >= 2][:5]
    lines      = []
    for a in top:
        label = {3: 'HIGH', 2: 'MEDIUM'}.get(int(a.get('riskcode', 0)), '?')
        lines.append(f"  • [{label}] {a.get('alert','?')}")
        lines.append(f"    {a.get('desc','')[:100].strip()}")
    sections.append(f"""🚨 OWASP ZAP — DAST [{status}]
{'=' * 52}
HIGH : {high}   MEDIUM : {medium}   LOW : {low}
{chr(10).join(lines) if lines else '  Aucune alerte HIGH/MEDIUM.'}
Seuil : HIGH > 0 ou MEDIUM > 1 = blocage
""")
    if high > 0 or medium > 1:
        issues.append(f"ZAP (HIGH={high}, MEDIUM={medium})")
else:
    sections.append("🚨 ZAP — rapport introuvable\n")


# ── Résultat final ────────────────────────────────────────
gate    = ("✅ GATE_PASS — Déploiement autorisé"
           if not issues else
           "🚫 GATE_FAIL — " + " | ".join(issues))
report  = "\n".join(sections) + "\n" + "=" * 52 + "\n" + gate

with open('security-summary.txt', 'w') as f:
    f.write(report)

print(report)
sys.exit(1 if issues else 0)