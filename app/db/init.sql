CREATE TABLE products (
  id          bigserial PRIMARY KEY,
  name        text        NOT NULL,
  category    text        NOT NULL,
  price       numeric(10,2) NOT NULL,
  description text        NOT NULL
);

INSERT INTO products (name, category, price, description)
SELECT 'Product ' || g,
       'cat-' || (g % 50),
       round((random() * 500)::numeric, 2),
       repeat('lorem ipsum ', 10)
FROM generate_series(1, 2000000) AS g;

CREATE INDEX products_category_price_idx ON products (category, price);

CREATE TABLE orders (
  id         text PRIMARY KEY,
  user_id    text        NOT NULL,
  items      jsonb       NOT NULL,
  total      numeric(10,2) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ANALYZE;
