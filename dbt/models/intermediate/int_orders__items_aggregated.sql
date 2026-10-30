-- The line arithmetic fct_orders and the order-level checks both need, still in the order's
-- minor units; the mart converts to euros once.
select
    order_id,
    count(*) as line_item_count,
    sum(quantity) as units,
    sum(gross_minor) as gross_minor,
    sum(discount_minor) as discount_minor,
    sum(net_minor) as net_minor,
    sum(realised_net_minor) as realised_net_minor,
    bool_or(is_returned) as has_return
from {{ ref('int_order_items__priced') }}
group by order_id
