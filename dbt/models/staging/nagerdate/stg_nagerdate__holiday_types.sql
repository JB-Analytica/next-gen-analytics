-- One row per element of the holiday's `types` list. dlt keeps the list as JSON on the holiday
-- row (child tables would carry no _dlt_load_id for source freshness).
with source as (

    select * from {{ source('nagerdate', 'holidays') }}
    where types is not null

),

unnested as (

    select
        _dlt_id as holiday_id,
        unnest(from_json(types, '["VARCHAR"]')) as holiday_type,
        generate_subscripts(from_json(types, '["VARCHAR"]'), 1) - 1 as list_index
    from source

),

renamed as (

    select
        md5(holiday_id || '|' || holiday_type) as holiday_type_id,
        holiday_id,
        holiday_type,
        list_index
    from unnested

)

select * from renamed
