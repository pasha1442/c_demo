### Kindlife
CREATE FULLTEXT INDEX productDescFullText FOR (p:Product) ON EACH [p.product_full_description, p.product_short_description]

CREATE FULLTEXT INDEX productTitleFullText FOR (p:Product) ON EACH [p.product_title]

CREATE FULLTEXT INDEX productInfoFullText FOR (p:Product) ON EACH [p.product_key_info, p.product_how_to_use]

CREATE VECTOR INDEX productDescriptionIndex FOR (p:Product) ON p.product_description_embedding OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}}

CREATE INDEX product_id_index FOR (p:Product) ON p.product_id

CREATE INDEX sku_code_index FOR (p:Product) ON p.sku_code

CREATE INDEX product_popularity_index FOR (p:Product) ON (p.product_popularity)

CREATE INDEX product_price_index FOR (p:Product) ON (p.product_selling_price)

CREATE VECTOR INDEX productCategoryVectorIndex FOR (p:Product) ON p.product_category_embedding