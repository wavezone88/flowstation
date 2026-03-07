import Stripe from 'stripe'
import { createClient } from '@supabase/supabase-js'

export const config = {
  api: {
    bodyParser: false,
  },
}

function getRawBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = []
    req.on('data', chunk => chunks.push(chunk))
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })
}

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY)

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
)

function mapPriceToTier(unitAmount) {
  if (unitAmount === 999) return { tier: 'pro', tierInternal: 'regular' }
  if (unitAmount === 1499) return { tier: 'elite', tierInternal: 'premium' }
  return null
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).send('Method Not Allowed')
  }

  const sig = req.headers['stripe-signature']

  let event

  try {
    const buf = await getRawBody(req)
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

    let result = mapPriceToTier(session.amount_total)

    if (!result && session.subscription) {
      try {
        const subscription = await stripe.subscriptions.retrieve(session.subscription, {
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

    const { error: profileError } = await supabase
      .from('profiles')
      .update({ tier: tierInternal })
      .eq('email', email)

    if (profileError) {
      console.error('Supabase profile update error:', profileError)
    }

    const { data: userList, error: listError } = await supabase.auth.admin.listUsers({
      page: 1,
      perPage: 1000
    })

    if (!listError && userList?.users) {
      const user = userList.users.find(u => u.email?.toLowerCase() === email.toLowerCase())
      if (user) {
        const { error: metaError } = await supabase.auth.admin.updateUserById(user.id, {
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
}
