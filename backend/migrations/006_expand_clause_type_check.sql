-- Expand clause_type CHECK constraint to include new types from ADR-006
-- Previous: 15 types, New: 23 types (added non_compete, data_protection,
-- audit_rights, representations, insurance, exclusivity, service_levels, change_of_control)

ALTER TABLE clauses DROP CONSTRAINT IF EXISTS clauses_clause_type_check;

ALTER TABLE clauses ADD CONSTRAINT clauses_clause_type_check
CHECK (clause_type IN (
    'indemnification', 'limitation_of_liability', 'payment_terms', 'insurance',
    'termination', 'force_majeure', 'service_levels', 'change_of_control',
    'intellectual_property', 'confidentiality', 'data_protection',
    'non_compete', 'exclusivity',
    'warranty', 'dispute_resolution', 'audit_rights', 'governing_law', 'representations',
    'assignment', 'notice', 'amendment', 'entire_agreement',
    'other'
));
