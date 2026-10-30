with customers as (

    select * from {{ ref('stg_noordkust__customers') }}

),

orders as (

    select * from {{ ref('fct_orders') }}

),

order_history as (

    select
        customer_id,
        count(*) filter (where not is_cancelled) as lifetime_orders,
        sum(realised_net_amount_eur) as lifetime_realised_net_revenue_eur,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date
    from orders
    group by customer_id

),

final as (

    select
        customers.customer_id,
        customers.first_name,
        customers.last_name,
        customers.email,
        customers.country_code,
        customers.city,
        customers.is_marketing_opt_in,
        customers.created_at,
        cast(customers.created_at as date) as created_date,
        coalesce(order_history.lifetime_orders, 0) as lifetime_orders,
        coalesce(order_history.lifetime_realised_net_revenue_eur, 0)
            as lifetime_realised_net_revenue_eur,
        order_history.first_order_date,
        order_history.last_order_date
    from customers
    left join order_history on customers.customer_id = order_history.customer_id

)

select * from final
