with orders as (

    select
        order_id,
        currency,
        cast(ordered_at as date) as order_date
    from {{ ref('stg_noordkust__orders') }}

),

rates as (

    select rate_date, quote_currency, eur_rate
    from {{ ref('stg_frankfurter__rates') }}

),

first_rate as (

    select quote_currency, min(rate_date) as rate_date
    from rates
    group by quote_currency

),

-- As-of join: the latest ECB rate published on or before the order date. The ECB publishes on
-- business days only, so weekends and holidays pick up the previous business day's rate.
as_of as (

    select
        orders.order_id,
        rates.rate_date as fx_rate_date,
        rates.eur_rate,
        row_number() over (
            partition by orders.order_id order by rates.rate_date desc
        ) as recency
    from orders
    inner join rates
        on orders.currency = rates.quote_currency
        and rates.rate_date <= orders.order_date

),

final as (

    select
        orders.order_id,
        orders.currency,
        orders.order_date,
        case
            when orders.currency = 'EUR' then 1.0
            -- An order older than the first published rate takes that first rate.
            else coalesce(as_of.eur_rate, earliest.eur_rate)
        end as fx_rate,
        case
            when orders.currency = 'EUR' then orders.order_date
            else coalesce(as_of.fx_rate_date, earliest.rate_date)
        end as fx_rate_date
    from orders
    left join as_of on orders.order_id = as_of.order_id and as_of.recency = 1
    left join first_rate on orders.currency = first_rate.quote_currency
    left join rates as earliest
        on first_rate.quote_currency = earliest.quote_currency
        and first_rate.rate_date = earliest.rate_date

)

select * from final
