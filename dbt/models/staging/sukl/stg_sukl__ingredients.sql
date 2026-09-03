-- INN normalization strategy for SÚKL NAZEV_INN (Latin pharmacopoeial form):
--   1. usan_inn_divergences seed: explicit alias→INN mappings take precedence.
--      This covers known Latin forms (paracetamolum→paracetamol) and USAN divergences
--      (acetaminophen→paracetamol). Extend the seed for newly discovered forms.
--   2. Fallback: lower(trim(NAZEV_INN)) — raw lowercased Latin form.
--      Full automated suffix stripping (e.g. stripping -um) is deferred because
--      element-based names (lithium) and salt forms (ibuprofeni lysini) require
--      case-by-case handling. Unresolved Latin forms are flagged by inn_needs_review.

with source as (
    select *
    from {{ source('bronze', 'sukl_ingredients') }}
    where _batch_id = (select max(_batch_id) from {{ source('bronze', 'sukl_ingredients') }})
),

usan_map as (
    select
        lower(trim(alias)) as alias_norm,
        inn
    from {{ ref('usan_inn_divergences') }}
),

normalized as (
    select
        trim(s."KOD_LATKY")                as ingredient_code,
        trim(s."NAZEV")                    as name_cz,
        trim(s."NAZEV_EN")                 as name_en,
        s."NAZEV_INN"                      as inn_latin,
        lower(trim(s."NAZEV_INN"))         as inn_latin_lower,
        coalesce(
            m.inn,
            lower(trim(s."NAZEV_INN"))
        )                                  as inn_normalized,
        m.inn is null                      as inn_needs_review,
        s._batch_id,
        s._source_file,
        s._load_ts
    from source s
    left join usan_map m
        on lower(trim(s."NAZEV_INN")) = m.alias_norm
    where s."KOD_LATKY" is not null
        and trim(s."KOD_LATKY") != ''
        and s."NAZEV_INN" is not null
        and trim(s."NAZEV_INN") != ''
)

select * from normalized
