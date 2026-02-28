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
      console.error('No email found in session', session.id)
      return res.status(200).json({ received: true })
    }

    const TIER_MAP = { 999: 'pro', 1999: 'elite' }
    const tier = TIER_MAP[session.amount_total]

    if (!tier) {
      console.warn(`Unrecognized amount ${session.amount_total} for session ${session.id}, skipping tier update`)
      return res.status(200).json({ received: true })
    }

    const { error } = await supabase
      .from('profiles')
      .update({ tier })
      .eq('email', email)

    if (error) {
      console.error('Supabase update error:', error)
    } else {
      console.log(`Upgraded ${email} to ${tier}`)
    }
  }

  return res.status(200).json({ received: true })
}
