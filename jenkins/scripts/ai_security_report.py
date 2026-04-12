#!/usr/bin/env python3
"""
AI Security Report Generator
Uses OpenRouter DeepSeek to analyze security reports
and generate a detailed email with corrections
"""

import json
import os
import sys
import requests
from datetime import datetime
from pathlib import Path


def load_report(path: str) -> dict | str:
    """Charge le rapport et réduit sa taille pour l'IA"""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())

        # --- TRIVY : ne garder que les vulnérabilités CRITICAL/HIGH ---
        if isinstance(data, dict) and "Results" in data:
            vulns = []
            for result in data.get("Results", []):
                for v in result.get("Vulnerabilities") or []:
                    if v.get("Severity") in ("CRITICAL", "HIGH"):
                        vulns.append({
                            "id":    v.get("VulnerabilityID"),
                            "pkg":   v.get("PkgName"),
                            "ver":   v.get("InstalledVersion"),
                            "fix":   v.get("FixedVersion"),
                            "sev":   v.get("Severity"),
                            "title": v.get("Title", "")[:120],
                        })
            return {"vulnerabilities": vulns[:30]}  # 30 max

        # --- GITLEAKS : liste de secrets, on coupe à 10 ---
        if isinstance(data, list):
            return [
                {
                    "rule":   s.get("RuleID") or s.get("rule"),
                    "file":   s.get("File")   or s.get("file"),
                    "line":   s.get("StartLine") or s.get("line"),
                    "secret": (s.get("Secret") or s.get("secret") or "")[:40],
                }
                for s in data[:10]
            ]

        # --- BANDIT : ne garder que HIGH/MEDIUM, 20 max ---
        if isinstance(data, dict) and "results" in data:
            issues = [
                {
                    "test":     i.get("test_id"),
                    "sev":      i.get("issue_severity"),
                    "conf":     i.get("issue_confidence"),
                    "text":     i.get("issue_text", "")[:120],
                    "file":     i.get("filename"),
                    "line":     i.get("line_number"),
                }
                for i in data["results"]
                if i.get("issue_severity") in ("HIGH", "MEDIUM")
            ]
            return {"results": issues[:20], "metrics": data.get("metrics", {})}

        # --- ZAP : alertes triées par risk, 20 max ---
        if isinstance(data, dict) and "site" in data:
            alerts = []
            for site in data.get("site", []):
                for alert in site.get("alerts", []):
                    if int(alert.get("riskcode", 0)) >= 2:  # Medium+
                        alerts.append({
                            "name":     alert.get("name"),
                            "risk":     alert.get("riskdesc"),
                            "solution": alert.get("solution", "")[:200],
                            "count":    alert.get("count"),
                            "url":      (alert.get("instances") or [{}])[0].get("uri", "")[:100],
                        })
            return {"alerts": alerts[:20]}

        return data  # fallback : retourner tel quel

    except json.JSONDecodeError:
        return p.read_text()[:3000]  # texte brut : couper à 3000 chars

def build_analysis_prompt(reports: dict) -> str:
    """Build the prompt for DeepSeek"""
    return f"""
Tu es un expert en cybersécurité DevSecOps.
Analyse ces rapports de sécurité d'un pipeline CI/CD Jenkins
et génère un rapport détaillé en français.

=== RAPPORTS DE SÉCURITÉ ===

--- GITLEAKS (Secrets détectés) ---
{json.dumps(reports.get('gitleaks', {}), indent=2, ensure_ascii=False)}

--- BANDIT (SAST Python) ---
{json.dumps(reports.get('bandit', {}), indent=2, ensure_ascii=False)}

--- TRIVY (Vulnérabilités image Docker) ---
{json.dumps(reports.get('trivy', {}), indent=2, ensure_ascii=False)}

--- ZAP (DAST Pentest) ---
{json.dumps(reports.get('zap', {}), indent=2, ensure_ascii=False)}

=== INSTRUCTIONS ===

Génère un rapport JSON avec exactement cette structure:
{{
  "verdict": "BLOQUÉ" ou "AUTORISÉ",
  "score_securite": number between 0 and 100,
  "resume_executif": "2-3 phrases résumant la situation",
  "statistiques": {{
    "secrets_detectes": number,
    "vulnerabilites_critiques": number,
    "vulnerabilites_hautes": number,
    "problemes_sast": number,
    "alertes_dast": number
  }},
  "problemes_critiques": [
    {{
      "outil": "nom de l'outil",
      "severite": "CRITIQUE/HAUTE/MOYENNE/BASSE",
      "description": "description claire du problème",
      "fichier": "fichier concerné si applicable",
      "ligne": "ligne si applicable",
      "correction": "comment corriger ce problème précisément",
      "exemple_code": "exemple de code corrigé si applicable"
    }}
  ],
  "recommandations_prioritaires": [
    "action 1 à faire immédiatement",
    "action 2",
    "action 3"
  ],
  "bonnes_pratiques": [
    "conseil 1 pour améliorer la sécurité",
    "conseil 2"
  ]
}}

Réponds UNIQUEMENT avec le JSON. Aucun texte avant ou après.
"""


def call_deepseek(prompt: str, api_key: str) -> dict:
    """Call OpenRouter DeepSeek API"""
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jenkins.devsecops.lab",
            "X-Title": "DevSecOps Pipeline"
        },
        json={
            "model": "deepseek/deepseek-chat",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4000
        },
        timeout=120
    )

    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]

    # clean markdown fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        content = content.rsplit("```", 1)[0]

    return json.loads(content)


def generate_html_email(analysis: dict, build_info: dict) -> str:
    """Generate beautiful HTML email from AI analysis"""

    verdict = analysis.get("verdict", "INCONNU")
    score = analysis.get("score_securite", 0)
    is_blocked = verdict == "BLOQUÉ"

    header_color = "#DC2626" if is_blocked else "#1A2B4A"
    sub_color = "#FCA5A5" if is_blocked else "#93C5FD"
    verdict_icon = "🚫" if is_blocked else "✅"
    score_color = "#DC2626" if score < 50 else "#EA580C" if score < 75 else "#16A34A"

    # build critical issues HTML
    issues_html = ""
    for issue in analysis.get("problemes_critiques", []):
        sev = issue.get("severite", "INCONNUE")
        sev_colors = {
            "CRITIQUE": ("#DC2626", "#FEE2E2"),
            "HAUTE":    ("#EA580C", "#FFF7ED"),
            "MOYENNE":  ("#D97706", "#FFFBEB"),
            "BASSE":    ("#2563EB", "#EFF6FF")
        }
        sev_color, sev_bg = sev_colors.get(sev, ("#6B7280", "#F9FAFB"))

        code_section = ""
        if issue.get("exemple_code"):
            code_section = f"""
            <div style="background:#1e293b;border-radius:4px;padding:12px;margin-top:8px;">
                <p style="color:#94A3B8;font-size:11px;margin:0 0 6px;">
                    💡 Correction suggérée:
                </p>
                <pre style="color:#86EFAC;font-size:11px;margin:0;
                            white-space:pre-wrap;">{issue.get('exemple_code', '')}</pre>
            </div>
            """

        issues_html += f"""
        <div style="border:1px solid #E2E8F0;border-radius:6px;
                    margin-bottom:12px;overflow:hidden;">
            <div style="background:{sev_bg};padding:10px 14px;
                        border-left:4px solid {sev_color};
                        display:flex;justify-content:space-between;">
                <span style="font-weight:bold;color:{sev_color};
                             font-size:13px;">{issue.get('outil','')}</span>
                <span style="background:{sev_color};color:white;
                             padding:2px 8px;border-radius:12px;
                             font-size:11px;font-weight:bold;">{sev}</span>
            </div>
            <div style="padding:12px 14px;">
                <p style="margin:0 0 6px;font-size:13px;
                          color:#1e293b;">{issue.get('description','')}</p>
                {'<p style="margin:4px 0;font-size:12px;color:#6B7280;">📁 ' + issue.get('fichier','') + ' — ligne ' + str(issue.get('ligne','')) + '</p>' if issue.get('fichier') else ''}
                <div style="background:#F0FDF4;border-left:3px solid #16A34A;
                            padding:8px 12px;margin-top:8px;border-radius:0 4px 4px 0;">
                    <p style="margin:0;font-size:12px;color:#15803D;">
                        🔧 {issue.get('correction','')}
                    </p>
                </div>
                {code_section}
            </div>
        </div>
        """

    # build recommendations HTML
    reco_html = ""
    for i, reco in enumerate(analysis.get("recommandations_prioritaires", []), 1):
        reco_html += f"""
        <div style="display:flex;align-items:flex-start;margin-bottom:8px;">
            <span style="background:#1A2B4A;color:white;border-radius:50%;
                         width:22px;height:22px;display:inline-flex;
                         align-items:center;justify-content:center;
                         font-size:11px;font-weight:bold;
                         flex-shrink:0;margin-right:10px;">{i}</span>
            <p style="margin:0;font-size:13px;color:#1e293b;
                      line-height:1.5;">{reco}</p>
        </div>
        """

    # build best practices HTML
    bp_html = ""
    for bp in analysis.get("bonnes_pratiques", []):
        bp_html += f"""
        <div style="display:flex;align-items:flex-start;margin-bottom:6px;">
            <span style="color:#2563EB;margin-right:8px;flex-shrink:0;">→</span>
            <p style="margin:0;font-size:12px;color:#475569;">{bp}</p>
        </div>
        """

    stats = analysis.get("statistiques", {})

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#1e293b;
             margin:0;padding:0;background:#F8FAFC;">

<div style="max-width:700px;margin:0 auto;background:white;
            box-shadow:0 4px 6px rgba(0,0,0,0.07);">

    <!-- HEADER -->
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:{header_color};padding:32px 28px;">
        <tr><td>
            <h1 style="color:white;margin:0;font-size:24px;">
                {verdict_icon} Rapport DevSecOps — {verdict}
            </h1>
            <p style="color:{sub_color};margin:8px 0 0;font-size:14px;">
                {build_info.get('job_name','Pipeline')} —
                Build #{build_info.get('build_number','N/A')}
            </p>
            <p style="color:{sub_color};margin:4px 0 0;font-size:12px;">
                🕐 {datetime.now().strftime('%d/%m/%Y à %H:%M')}
            </p>
        </td></tr>
    </table>

    <!-- SCORE -->
    <table width="100%" cellpadding="0" cellspacing="0"
           style="padding:20px 28px;background:#F8FAFC;
                  border-bottom:1px solid #E2E8F0;">
        <tr>
            <td style="text-align:center;padding:0 12px;">
                <div style="font-size:42px;font-weight:bold;
                            color:{score_color};">{score}</div>
                <div style="font-size:11px;color:#6B7280;
                            text-transform:uppercase;">Score Sécurité /100</div>
            </td>
            <td style="padding:0 12px;border-left:1px solid #E2E8F0;">
                <table>
                    <tr>
                        <td style="font-size:12px;color:#6B7280;
                                   padding:3px 8px;">🔑 Secrets</td>
                        <td style="font-size:13px;font-weight:bold;
                                   color:#DC2626;">
                            {stats.get('secrets_detectes',0)}
                        </td>
                    </tr>
                    <tr>
                        <td style="font-size:12px;color:#6B7280;
                                   padding:3px 8px;">🔴 Critiques</td>
                        <td style="font-size:13px;font-weight:bold;
                                   color:#DC2626;">
                            {stats.get('vulnerabilites_critiques',0)}
                        </td>
                    </tr>
                    <tr>
                        <td style="font-size:12px;color:#6B7280;
                                   padding:3px 8px;">🟠 Hautes</td>
                        <td style="font-size:13px;font-weight:bold;
                                   color:#EA580C;">
                            {stats.get('vulnerabilites_hautes',0)}
                        </td>
                    </tr>
                    <tr>
                        <td style="font-size:12px;color:#6B7280;
                                   padding:3px 8px;">🔍 SAST</td>
                        <td style="font-size:13px;font-weight:bold;
                                   color:#D97706;">
                            {stats.get('problemes_sast',0)}
                        </td>
                    </tr>
                    <tr>
                        <td style="font-size:12px;color:#6B7280;
                                   padding:3px 8px;">🚨 DAST</td>
                        <td style="font-size:13px;font-weight:bold;
                                   color:#7C3AED;">
                            {stats.get('alertes_dast',0)}
                        </td>
                    </tr>
                </table>
            </td>
            <td style="padding:0 12px;border-left:1px solid #E2E8F0;">
                <p style="font-size:12px;color:#6B7280;margin:0 0 4px;">
                    <b>Pipeline</b>
                </p>
                <p style="font-size:13px;margin:0 0 8px;">
                    {build_info.get('job_name','N/A')}
                </p>
                <p style="font-size:12px;color:#6B7280;margin:0 0 4px;">
                    <b>Commit</b>
                </p>
                <p style="font-size:12px;font-family:monospace;
                          margin:0 0 8px;color:#475569;">
                    {build_info.get('git_commit','N/A')[:12]}
                </p>
                <p style="font-size:12px;color:#6B7280;margin:0 0 4px;">
                    <b>Branche</b>
                </p>
                <p style="font-size:13px;margin:0;">
                    {build_info.get('git_branch','N/A')}
                </p>
            </td>
        </tr>
    </table>

    <!-- RESUME EXECUTIF -->
    <div style="padding:20px 28px;border-bottom:1px solid #E2E8F0;">
        <h2 style="color:#1A2B4A;font-size:16px;margin:0 0 12px;">
            📋 Résumé Exécutif
        </h2>
        <div style="background:#F8FAFC;border-left:4px solid #2563EB;
                    padding:14px 16px;border-radius:0 6px 6px 0;">
            <p style="margin:0;font-size:14px;line-height:1.7;color:#1e293b;">
                {analysis.get('resume_executif','')}
            </p>
        </div>
    </div>

    <!-- PROBLEMES CRITIQUES -->
    <div style="padding:20px 28px;border-bottom:1px solid #E2E8F0;">
        <h2 style="color:#1A2B4A;font-size:16px;margin:0 0 16px;">
            🚨 Problèmes Détectés & Corrections
        </h2>
        {issues_html if issues_html else
         '<p style="color:#16A34A;font-size:13px;">✅ Aucun problème critique détecté</p>'}
    </div>

    <!-- RECOMMANDATIONS -->
    <div style="padding:20px 28px;border-bottom:1px solid #E2E8F0;">
        <h2 style="color:#1A2B4A;font-size:16px;margin:0 0 16px;">
            ⚡ Actions Prioritaires
        </h2>
        {reco_html}
    </div>

    <!-- BONNES PRATIQUES -->
    <div style="padding:20px 28px;border-bottom:1px solid #E2E8F0;">
        <h2 style="color:#1A2B4A;font-size:16px;margin:0 0 12px;">
            💡 Bonnes Pratiques
        </h2>
        {bp_html}
    </div>

    <!-- BUTTONS -->
    <div style="padding:20px 28px;border-bottom:1px solid #E2E8F0;">
        <a href="{build_info.get('build_url','')}console"
           style="display:inline-block;background:#1A2B4A;color:white;
                  padding:10px 18px;text-decoration:none;border-radius:4px;
                  font-size:13px;margin-right:8px;">
            📋 Logs Jenkins
        </a>
        <a href="{build_info.get('build_url','')}artifact/"
           style="display:inline-block;background:#0D9488;color:white;
                  padding:10px 18px;text-decoration:none;border-radius:4px;
                  font-size:13px;margin-right:8px;">
            📦 Rapports
        </a>
        <a href="{build_info.get('build_url','')}ZAP_20Security_20Report/"
           style="display:inline-block;background:#EA580C;color:white;
                  padding:10px 18px;text-decoration:none;border-radius:4px;
                  font-size:13px;">
            🚨 Rapport ZAP
        </a>
    </div>

    <!-- FOOTER -->
    <div style="background:#F1F5F9;padding:14px 28px;text-align:center;">
        <p style="font-size:11px;color:#94A3B8;margin:0;">
            DevSecOps Pipeline — Jenkins CI/CD —
            Analyse par DeepSeek via OpenRouter —
            {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </p>
    </div>

</div>
</body>
</html>
"""


def send_email_resend(api_key, to, subject, html, attachments):
    import base64
    attach_payload = []
    
    for att in attachments:
        path = Path(att["path"])
        # On vérifie si le fichier existe ET n'est pas vide
        if path.exists() and path.stat().st_size > 0:
            try:
                content = base64.b64encode(path.read_bytes()).decode()
                attach_payload.append({
                    "filename": att["name"], 
                    "content": content
                })
                print(f"📎 Pièce jointe ajoutée : {att['name']}")
            except Exception as e:
                print(f"⚠️ Impossible de lire {att['name']}: {e}")
        else:
            print(f"⚠️ Fichier ignoré (absent ou vide) : {att['name']}")

    payload = {
        "from": "DevSecOps Pipeline <onboarding@resend.dev>",
        "to": [to],
        "subject": subject,
        "html": html
    }

    # On n'ajoute la clé attachments QUE si on a des fichiers valides
    if attach_payload:
        payload["attachments"] = attach_payload

    print(f"📡 Tentative d'envoi à {to}...")
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}", 
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        if response.status_code in [200, 201]:
            print(f"✅ Email envoyé ! ID: {response.json().get('id')}")
            return True
        else:
            print(f"❌ ERREUR RESEND ({response.status_code}) : {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erreur réseau lors de l'envoi : {e}")
        return False


def main():
    # get env variables
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    resend_key     = os.environ.get("RESEND_API_KEY", "")
    to_email       = os.environ.get("REPORT_EMAIL", "amardjebabla10@gmail.com")
    workspace      = os.environ.get("WORKSPACE", ".")

    build_info = {
        "job_name":     os.environ.get("JOB_NAME", "Pipeline"),
        "build_number": os.environ.get("BUILD_NUMBER", "N/A"),
        "build_url":    os.environ.get("BUILD_URL", ""),
        "git_commit":   os.environ.get("GIT_COMMIT", "N/A"),
        "git_branch":   os.environ.get("GIT_BRANCH", "N/A"),
    }

    if not openrouter_key:
        print("❌ OPENROUTER_API_KEY manquant")
        sys.exit(1)

    if not resend_key:
        print("❌ RESEND_API_KEY manquant")
        sys.exit(1)

    # load all reports
    print("📂 Chargement des rapports...")
    reports = {
        "gitleaks": load_report(f"{workspace}/gitleaks-report.json"),
        "bandit":   load_report(f"{workspace}/bandit-report.json"),
        "trivy":    load_report(f"{workspace}/trivy-report.json"),
        "zap":      load_report(f"{workspace}/zap-report.json"),
    }

    # call deepseek
    print("🤖 Analyse par DeepSeek...")
    prompt   = build_analysis_prompt(reports)
    analysis = call_deepseek(prompt, openrouter_key)

    # save analysis
    analysis_path = f"{workspace}/ai-security-analysis.json"
    Path(analysis_path).write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False)
    )
    print("✅ Analyse sauvegardée")

    # generate html email
    print("📧 Génération de l'email...")
    html = generate_html_email(analysis, build_info)

    # save html for archive
    html_path = f"{workspace}/ai-security-report.html"
    Path(html_path).write_text(html)

    # build subject
    verdict = analysis.get("verdict", "INCONNU")
    score   = analysis.get("score_securite", 0)
    icon    = "🚫" if verdict == "BLOQUÉ" else "✅"
    subject = (
        f"{icon} [{build_info['job_name']}] "
        f"Build #{build_info['build_number']} — "
        f"{verdict} — Score: {score}/100"
    )

    # attachments
    attachments = [
        {"path": f"{workspace}/gitleaks-report.json", "name": "gitleaks-report.json"},
        {"path": f"{workspace}/bandit-report.json",   "name": "bandit-report.json"},
        {"path": f"{workspace}/trivy-report.json",    "name": "trivy-report.json"},
        {"path": f"{workspace}/zap-report.json",      "name": "zap-report.json"},
        {"path": analysis_path,                        "name": "ai-security-analysis.json"},
    ]

    # send email
    print("📤 Envoi de l'email...")
    send_email_resend(resend_key, to_email, subject, html, attachments)

    # exit with verdict
    if verdict == "BLOQUÉ":
        print("🚫 Déploiement bloqué par l'IA")
        sys.exit(1)

    print("🚀 Quality Gate passée")
    sys.exit(0)


if __name__ == "__main__":
    main()