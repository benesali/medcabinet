with source as (
    select *
    from {{ source('bronze', 'sukl_atc') }}
    where _batch_id = (select max(_batch_id) from {{ source('bronze', 'sukl_atc') }})
),

validated as (
    select
        trim("ATC")                                      as atc_code,
        trim("NAZEV")                                    as description_cz,
        trim("NAZEV_EN")                                 as description_en,
        -- ATC level from code length: 1→1, 3→2, 4→3, 5→4, 7→5
        case length(trim("ATC"))
            when 1 then 1
            when 3 then 2
            when 4 then 3
            when 5 then 4
            when 7 then 5
            else null
        end                                              as atc_level,
        -- Full level-5 codes must match [A-Z][0-9]{2}[A-Z]{2}[0-9]{2}
        trim("ATC") ~ '^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$' as is_level5_format_valid,
        _batch_id,
        _source_file,
        _load_ts
    from source
    where "ATC" is not null
        and trim("ATC") != ''
)

select * from validated
