from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)

# --- BASE DE DONNÉES ---
# CORRIGÉ : chemin absolu pour Render
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rencontre.db")

def get_db():
    """Établit une connexion SQLite avec accès par nom de colonne."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialise les tables si elles n'existent pas."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS utilisateur(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        sexe TEXT,
        ville TEXT,
        numero TEXT,
        attentes TEXT,
        attitude TEXT,
        heures_libre TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS match (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1_id INTEGER,
        user2_id INTEGER,
        statut TEXT DEFAULT 'en_attente',
        FOREIGN KEY(user1_id) REFERENCES utilisateur(id),
        FOREIGN KEY(user2_id) REFERENCES utilisateur(id)
    )""")

    conn.commit()
    conn.close()

# CORRIGÉ : init_db() au démarrage du serveur, pas seulement en local
init_db()

# --- LOGIQUE MÉTIER ---
def trouver_match(nouveau_id):
    """Algorithme de matching : Ville + Sexe Opposé + Attitude."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM utilisateur WHERE id=?", (nouveau_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return

    cursor.execute("""
        SELECT id FROM utilisateur
        WHERE id != ?
        AND LOWER(sexe) != LOWER(?)
        AND LOWER(ville) = LOWER(?)
    """, (user["id"], user["sexe"], user["ville"]))

    potential_matches = cursor.fetchall()

    for m in potential_matches:
        # Évite les doublons de match
        cursor.execute("""
            SELECT id FROM match
            WHERE (user1_id=? AND user2_id=?) OR (user1_id=? AND user2_id=?)
        """, (user["id"], m["id"], m["id"], user["id"]))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO match (user1_id, user2_id) VALUES (?, ?)",
                (user["id"], m["id"])
            )

    conn.commit()
    conn.close()

# --- ROUTES ---

@app.route('/')
def serve_frontend():
    """Affiche la page principale."""
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    """Enregistre un utilisateur et lance le matching."""
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Données manquantes."}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO utilisateur (nom, sexe, ville, numero, attentes, attitude, heures_libre)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('nom'),
            data.get('sexe'),
            data.get('ville'),
            data.get('numero'),
            data.get('attentes'),
            data.get('attitude'),
            data.get('heures_libre', 'Non spécifié')
        ))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        trouver_match(user_id)
        return jsonify({"status": "success", "message": "Profil créé !"}), 201
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/stats', methods=['GET'])
def statistiques():
    """Prépare les données pour Chart.js."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ville, COUNT(*) as total
        FROM utilisateur
        GROUP BY ville
        ORDER BY total DESC
        LIMIT 5
    """)
    villes_raw = cursor.fetchall()
    classement_villes = [{"ville": r["ville"], "utilisateurs": r["total"]} for r in villes_raw]

    cursor.execute("""
        SELECT u.nom, COUNT(m.id) as nb
        FROM utilisateur u
        LEFT JOIN match m ON u.id = m.user1_id OR u.id = m.user2_id
        GROUP BY u.id
        ORDER BY nb DESC
        LIMIT 5
    """)
    users_raw = cursor.fetchall()
    classement_users = [{"nom": r["nom"], "matchs": r["nb"]} for r in users_raw]

    conn.close()

    if not classement_villes:
        classement_villes = [{"ville": "Aucune donnée", "utilisateurs": 0}]
    if not classement_users:
        classement_users = [{"nom": "En attente", "matchs": 0}]

    return jsonify({
        "classement_utilisateurs": classement_users,
        "classement_villes": classement_villes
    })

if __name__ == '__main__':
    # CORRIGÉ : debug=False en production
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)