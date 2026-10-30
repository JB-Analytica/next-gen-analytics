{#- Booked and realised revenue are one definition, pinned against the flags:
    realised equals booked unless the order is cancelled (then zero), and a line's realised
    amount is never more than its booked amount. -#}

select order_id, net_amount_eur, realised_net_amount_eur, is_cancelled
from {{ ref('fct_orders') }}
where (is_cancelled and realised_net_amount_eur != 0)
    or realised_net_amount_eur > net_amount_eur
    or (not is_cancelled and not has_return and realised_net_amount_eur != net_amount_eur)
