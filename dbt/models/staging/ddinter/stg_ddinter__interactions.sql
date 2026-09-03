-- Severity is normalized to CAVEAT vocabulary (lowercase).
-- 'Unknown' level → null (not a severity class — filtered downstream).
-- Self-interactions excluded. Drug name INN resolution happens in intermediate models.

with source as (
    select *
    from {{ source('bronze', 'ddinter_interactions') }}
    where _batch_id = (select max(_batch_id) from {{ source('bronze', 'ddinter_interactions') }})
),

normalized as (
    select
        trim("Drug1")                      as drug1_name,
        trim("Drug2")                      as drug2_name,
        lower(trim("Drug1"))               as drug1_name_lower,
        lower(trim("Drug2"))               as drug2_name_lower,
        "Level"                            as severity_raw,
        case lower(trim("Level"))
            when 'major'    then 'major'
            when 'moderate' then 'moderate'
            when 'minor'    then 'minor'
            else null
        end                                as severity,
        trim("Interaction")                as mechanism,
        _batch_id,
        _source_file,
        _load_ts
    from source
    where trim("Drug1") is not null
        and trim("Drug2") is not null
        and lower(trim("Drug1")) != lower(trim("Drug2"))
)

select * from normalized
