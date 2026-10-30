with holidays as (

    select * from {{ ref('stg_nagerdate__holidays') }}

),

counties as (

    select holiday_id, count(*) as county_count
    from {{ ref('stg_nagerdate__holiday_counties') }}
    group by holiday_id

),

flagged as (

    select
        holidays.country_code,
        holidays.holiday_date,
        holidays.holiday_name,
        -- National = not limited to any region.
        coalesce(counties.county_count, 0) = 0 as is_national
    from holidays
    left join counties on holidays.holiday_id = counties.holiday_id

),

final as (

    select
        country_code || '-' || cast(holiday_date as varchar) as country_date_id,
        country_code,
        holiday_date,
        min(holiday_name) as holiday_name,
        count(*) as holiday_count,
        bool_or(is_national) as is_national
    from flagged
    group by country_code, holiday_date

)

select * from final
