-- One row per element of the holiday's `counties` list. dlt keeps the list as JSON on the holiday
-- row (child tables would carry no _dlt_load_id for source freshness).
with source as (

    select * from {{ source('nagerdate', 'holidays') }}
    where counties is not null

),

unnested as (

    select
        _dlt_id as holiday_id,
        unnest(from_json(counties, '["VARCHAR"]')) as county_code,
        generate_subscripts(from_json(counties, '["VARCHAR"]'), 1) - 1 as list_index
    from source

),

renamed as (

    select
        md5(holiday_id || '|' || county_code) as holiday_county_id,
        holiday_id,
        county_code,
        list_index
    from unnested

)

select * from renamed
