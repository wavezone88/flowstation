import Stripe from 'stripe'
import { createClient } from '@supabase/supabase-js'
import { buffer } from 'micro'

export const config = {
  api: {
    bodyParser: false,
  },
}

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY)

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
)

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).send('Method Not Allowed')
  }

  const sig = req.headers['stripe-signature']

  let event

  try {
    const buf = await buffer(req)
    event = stripe.webhooks.constructEvent(
      buf,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET
    )
  } catch (err) {
    console.error('Webhook signature verification failed.', err.message)
    return res.status(400).send(`Webhook Error: ${err.message}`)
  }

  if (event.type === 'checkout.session.completed') {
    const session = event.data.object

    const email =
      session.customer_details?.email ||
      session.customer_email

    if (!email) {
      console.error('No email found in checkout session')
      return res.status(200).json({ received: true })
    }

    let tier = 'basic'
    let tierInternal = 'basic'

    if (session.amount_total === 999) {
      tier = 'pro'
      tierInternal = 'regular'
    } else if (session.amount_total === 1499) {
      tier = 'elite'
      tierInternal = 'premium'
    } else if (session.amount_total === 0 && session.subscription) {
      try {
        const subscription = await stripe.subscriptions.retrieve(session.subscription, {
          expand: ['items.data.price']
        })
        const unitAmount = subscription.items?.data?.[0]?.price?.unit_amount
        if (unitAmount === 999) {
          tier = 'pro'
          tierInternal = 'regular'
        } else if (unitAmount === 1499) {
          tier = 'elite'
          tierInternal = 'premium'
        }
      } catch (e) {
        console.error('Failed to retrieve subscription:', e.message)
      }
    }

    if (tierInternal === 'basic') {
      console.log(`Checkout completed for ${email} but could not determine tier (amount_total: ${session.amount_total})`)
      return res.status(200).json({ received: true })
    }

    const { error: profileError } = await supabase
      .from('profiles')
      .update({ tier: tierInternal })
      .eq('email', email)

    if (profileError) {
      console.error('Supabase profile update error:', profileError)
    }

    const { data: users, error: listError } = await supabase.auth.admin.listUsers()

    if (!listError && users?.users) {
      const user = users.users.find(u => u.email?.toLowerCase() === email.toLowerCase())
      if (user) {
        const { error: metaError } = await supabase.auth.admin.updateUserById(user.id, {
          user_metadata: { tier: tierInternal }
        })
        if (metaError) {
          console.error('Supabase user_metadata update error:', metaError)
        } else {
          console.log(`Upgraded ${email} to ${tierInternal} (${tier}) in both profiles and user_metadata`)
        }
      } else {
        console.log(`User ${email} not found in auth - profile table updated to ${tierInternal}`)
      }
    }
  }

  return res.status(200).json({ received: true })
}
