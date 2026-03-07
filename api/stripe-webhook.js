import Stripe from 'stripe'
import { createClient } from '@supabase/supabase-js'

export const config = {
  api: {
    bodyParser: false,
  },
}

function getRawBody(req) {
  if (req.body) {
    return Promise.resolve(typeof req.body === 'string' ? Buffer.from(req.body) : Buffer.isBuffer(req.body) ? req.body : Buffer.from(JSON.stringify(req.body)))
  }
  return new Promise((resolve, reject) => {
    const chunks = []
    req.on('data', chunk => chunks.push(chunk))
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })
}

let stripe = null
let supabase = null

function getStripe() {
  if (!stripe) stripe = new Stripe(process.env.STRIPE_SECRET_KEY)
  return stripe
}

function getSupabase() {
  if (!supabase) supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY)
  return supabase
}

function mapPriceToTier(unitAmount) {
  if (unitAmount === 999) return { tier: 'pro', tierInternal: 'regular' }
  if (unitAmount === 1499) return { tier: 'elite', tierInternal: 'premium' }
  return null
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).send('Method Not Allowed')
  }

  try {
    const sig = req.headers['stripe-signature']

    if (!process.env.STRIPE_SECRET_KEY || !process.env.STRIPE_WEBHOOK_SECRET || !process.env.SUPABASE_URL || !process.env.SUPABASE_SERVICE_ROLE_KEY) {
      console.error('Missing env vars:', {
        hasStripeKey: !!process.env.STRIPE_SECRET_KEY,
        hasWebhookSecret: !!process.env.STRIPE_WEBHOOK_SECRET,
        hasSupabaseUrl: !!process.env.SUPABASE_URL,
        hasServiceKey: !!process.env.SUPABASE_SERVICE_ROLE_KEY
      })
      return res.status(500).json({ error: 'Server configuration error' })
    }

    const st = getStripe()
    const sb = getSupabase()

    let event

    try {
      const buf = await getRawBody(req)
      event = st.webhooks.constructEvent(
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

      let result = mapPriceToTier(session.amount_total)

      if (!result && session.subscription) {
        try {
          const subscription = await st.subscriptions.retrieve(session.subscription, {
            expand: ['items.data.price']
          })
          const unitAmount = subscription.items?.data?.[0]?.price?.unit_amount
          if (unitAmount) {
            result = mapPriceToTier(unitAmount)
          }
        } catch (e) {
          console.error('Failed to retrieve subscription:', e.message)
        }
      }

      if (!result) {
        console.log(`Checkout completed for ${email} but could not determine tier (amount_total: ${session.amount_total})`)
        return res.status(200).json({ received: true })
      }

      const { tierInternal } = result

      const { error: profileError } = await sb
        .from('profiles')
        .update({ tier: tierInternal })
        .eq('email', email)

      if (profileError) {
        console.error('Supabase profile update error:', profileError)
      }

      const { data: userList, error: listError } = await sb.auth.admin.listUsers({
        page: 1,
        perPage: 1000
      })

      if (!listError && userList?.users) {
        const user = userList.users.find(u => u.email?.toLowerCase() === email.toLowerCase())
        if (user) {
          const { error: metaError } = await sb.auth.admin.updateUserById(user.id, {
            user_metadata: { tier: tierInternal }
          })
          if (metaError) {
            console.error('Supabase user_metadata update error:', metaError)
          } else {
            console.log(`Upgraded ${email} to ${tierInternal} in both profiles and user_metadata`)
          }
        } else {
          console.log(`User ${email} not found in auth users - profile table updated to ${tierInternal}`)
        }
      }
    }

    return res.status(200).json({ received: true })
  } catch (err) {
    console.error('Webhook handler error:', err)
    return res.status(500).json({ error: 'Internal server error' })
  }
}
