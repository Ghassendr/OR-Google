require('dotenv').config();
const express = require('express');
const mysql = require('mysql2/promise');
const { v4: uuidv4 } = require('uuid');
const nodemailer = require('nodemailer');
const jwt = require('jsonwebtoken');
const cors = require('cors');
const cookieParser = require('cookie-parser');
const rateLimit = require('express-rate-limit');

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(express.json());
app.use(cookieParser());
app.use(cors({
    origin: process.env.FRONTEND_URL || 'http://localhost:5173',
    credentials: true
}));

// MySQL Database Pool
const pool = mysql.createPool({
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME,
    port: process.env.DB_PORT || 3307,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
});

// Nodemailer setup with MailHog
const transporter = nodemailer.createTransport({
    host: process.env.MAIL_HOST || 'localhost',
    port: process.env.MAIL_PORT || 1025,
    ignoreTLS: true,
});

// Rate limiting for the auth route
const authLimiter = rateLimit({
    windowMs: 60 * 60 * 1000, 
    max: 10, // Increased slightly for testing
    message: { error: 'Trop de tentatives, veuillez réessayer dans une heure.' }
});

// 1. Request Magic Link
app.post('/api/auth/request-link', authLimiter, async (req, res) => {
    const { email } = req.body;
    if (!email) return res.status(400).json({ error: 'Email requis' });

    try {
        const [rows] = await pool.query('SELECT * FROM professeur WHERE email = ?', [email]);
        
        if (rows.length === 0) {
            // As requested: explicit error if email is not found
            return res.status(404).json({ error: 'Mail incorrecte' });
        }
        
        const prof = rows[0];
        const token = uuidv4();
        // Set expiry to 15 mins
        const expiresAt = new Date(Date.now() + 15 * 60 * 1000);

        // Store token
        await pool.query(
            'INSERT INTO magic_tokens (prof_id, token, expires_at) VALUES (?, ?, ?)',
            [prof.id, token, expiresAt]
        );

        const verifyUrl = `${process.env.FRONTEND_URL || 'http://localhost:5173'}/verify?token=${token}`;
        
        // Send email
        const mailOptions = {
            from: '"Administration ISSAT" <admin@issatso.com>',
            to: email,
            subject: 'Lien de connexion - Gestion des Absences',
            html: `<p>Bonjour ${prof.full_name},</p>
                   <p>Voici votre lien sécurisé pour vous connecter au portail enseignant, valide 15 minutes :</p>
                   <br/>
                   <a href="${verifyUrl}" style="background-color: #4a75b4; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Se connecter</a>
                   <br/><br/>
                   <p>Si vous n'avez pas demandé ce lien, veuillez ignorer cet e-mail.</p>`
        };

        await transporter.sendMail(mailOptions);
        res.json({ message: 'Un e-mail de vérification a été envoyé.' });
    } catch (error) {
        console.error('Error in /request-link:', error);
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

// 2. Verify Token and Set JWT
app.post('/api/auth/verify', async (req, res) => {
    const { token } = req.body;
    if (!token) return res.status(400).json({ error: 'Token requis' });

    try {
        const [tokenRows] = await pool.query(
            'SELECT * FROM magic_tokens WHERE token = ? AND used = FALSE',
            [token]
        );

        if (tokenRows.length === 0) {
            return res.status(401).json({ error: 'Lien invalide ou déjà utilisé.' });
        }

        const magicToken = tokenRows[0];
        
        if (new Date(magicToken.expires_at) < new Date()) {
            return res.status(401).json({ error: 'Le lien a expiré.' });
        }

        // Mark as used
        await pool.query('UPDATE magic_tokens SET used = TRUE WHERE id = ?', [magicToken.id]);

        // Get Prof
        const [profRows] = await pool.query('SELECT * FROM professeur WHERE id = ?', [magicToken.prof_id]);
        const prof = profRows[0];

        if(!prof) {
             return res.status(404).json({ error: 'Utilisateur introuvable.' });
        }

        // Issue JWT
        const jwtToken = jwt.sign(
            { id: prof.id, email: prof.email, full_name: prof.full_name },
            process.env.JWT_SECRET,
            { expiresIn: '8h' }
        );

        res.cookie('token', jwtToken, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
            maxAge: 8 * 60 * 60 * 1000
        });

        res.json({ message: 'Authentifié avec succès', user: { id: prof.id, full_name: prof.full_name, email: prof.email } });
    } catch (error) {
        console.error('Error in /verify:', error);
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

// Auth Middleware
const authMiddleware = (req, res, next) => {
    const token = req.cookies.token;
    if (!token) return res.status(401).json({ error: 'Non autorisé. Veuillez vous connecter.' });

    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        req.user = decoded;
        next();
    } catch (error) {
        return res.status(401).json({ error: 'Token invalide' });
    }
};

// Get current user via cookie
app.get('/api/auth/me', authMiddleware, async (req, res) => {
    try {
        const [profRows] = await pool.query('SELECT id, full_name, email, grade, charge, rest_charger FROM professeur WHERE id = ?', [req.user.id]);
        if(profRows.length === 0) return res.status(404).json({error: 'Utilisateur non trouvé'});
        
        const [declarationsRows] = await pool.query('SELECT * FROM declarations WHERE prof_id = ?', [req.user.id]);
        
        res.json({
            user: profRows[0],
            declarations: declarationsRows
        });
    } catch(err) {
        res.status(500).json({error: 'Erreur serveur'});
    }
});

// Logout
app.post('/api/auth/logout', (req, res) => {
    res.clearCookie('token');
    res.json({ message: 'Déconnecté' });
});

// Submit declarations (Absences)
app.post('/api/declarations', authMiddleware, async (req, res) => {
    const { selections } = req.body;
    if (!Array.isArray(selections)) {
        return res.status(400).json({ error: 'Format invalide' });
    }

    const connection = await pool.getConnection();
    try {
        await connection.beginTransaction();

        // Delete existing declarations (1 requête)
        await connection.query('DELETE FROM declarations WHERE prof_id = ?', [req.user.id]);

        // Batch INSERT : toutes les séances en une seule requête
        if (selections.length > 0) {
            const values = selections.map(slot => [req.user.id, slot.jour, slot.slot_name]);
            await connection.query(
                'INSERT INTO declarations (prof_id, jour, seance) VALUES ?',
                [values]
            );
        }

        await connection.commit();
        connection.release();

        res.json({ message: 'Indisponibilités enregistrées avec succès' });
    } catch (error) {
        await connection.rollback();
        connection.release();
        console.error('Error saving declarations:', error);
        res.status(500).json({ error: 'Erreur serveur lors de la sauvegarde.' });
    }
});

app.listen(PORT, () => {
    console.log(`Serveur démarré sur le port ${PORT}`);
});
