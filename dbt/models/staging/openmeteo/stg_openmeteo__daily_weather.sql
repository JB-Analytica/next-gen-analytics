with source as (

    select * from {{ source('openmeteo', 'daily_weather') }}

),

renamed as (

    select
        country_code || '-' || cast(date as varchar) as weather_id,
        country_code,
        city as city_name,
        latitude,
        longitude,
        date as weather_date,
        temperature_2m_max as temperature_max_c,
        temperature_2m_min as temperature_min_c,
        temperature_2m_mean as temperature_mean_c,
        precipitation_sum as precipitation_mm,
        rain_sum as rain_mm,
        wind_speed_10m_max as wind_speed_max_kmh,
        sunshine_duration / 3600.0 as sunshine_hours,
        _dlt_load_id as dlt_load_id
    from source

)

select * from renamed
