
-- SQLite Schema for the Discord Bot Project

-- Table to store information about Discord users
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    discriminator TEXT NOT NULL,
    avatar_url TEXT
);

-- Table to store information about the products available for purchase
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL,
    role_id INTEGER NOT NULL UNIQUE, -- The Discord role associated with this product
    is_active INTEGER DEFAULT 1
);

-- Table to store information about user orders
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(user_id),
    product_id INTEGER REFERENCES products(product_id),
    purchase_date TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'PENDING', -- PENDING, COMPLETED, FAILED
    payment_id INTEGER REFERENCES payments(payment_id)
);

-- Table to store payment information
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,
    value REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

-- Table to store information about support tickets
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(user_id),
    channel_id INTEGER NOT NULL UNIQUE,
    status TEXT DEFAULT 'OPEN', -- OPEN, CLOSED
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT
);

-- Table to store the transcript of each ticket
CREATE TABLE IF NOT EXISTS ticket_transcripts (
    transcript_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER REFERENCES tickets(ticket_id),
    content TEXT NOT NULL
);

-- Table to store system telemetry and log traces locally
CREATE TABLE IF NOT EXISTS sys_trace_stream (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    payload TEXT NOT NULL
);
