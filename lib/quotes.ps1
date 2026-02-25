# quotes.ps1 - Quotes, roasts, celebrations, greetings

function Get-TimeGreeting {
    $hour = (Get-Date).Hour
    switch ($hour) {
        { $_ -ge 5 -and $_ -lt 12 }  { return (Get-Random -InputObject @(
            "Good morning, sunshine!"
            "Rise and grind!"
            "Morning! Fresh start, fresh mind."
            "Top of the morning to you!"
            "New day. New energy. Let's go."
        ))}
        { $_ -ge 12 -and $_ -lt 17 } { return (Get-Random -InputObject @(
            "Good afternoon! Keep the momentum."
            "Afternoon check-in - you are doing great."
            "Halfway through the day, keep pushing!"
            "Hope your afternoon is productive!"
            "Afternoon focus mode activated."
        ))}
        { $_ -ge 17 -and $_ -lt 21 } { return (Get-Random -InputObject @(
            "Good evening! Wrapping up?"
            "Evening mode - time to wind down."
            "Hope you had a great day!"
            "Evening check - anything left to knock out?"
            "Almost done for the day!"
        ))}
        default { return (Get-Random -InputObject @(
            "Burning the midnight oil?"
            "Late night productivity hits different."
            "Night owl mode activated."
            "The quiet hours - prime focus time."
            "Still at it? Respect."
        ))}
    }
}

function Get-MotivationalQuote {
    # Each quote is a hashtable with Text and Author
    # Mix of deep, fun, philosophical, scientific
    $quotes = @(
        # Einstein
        @{ Text = "Imagination is more important than knowledge. Knowledge is limited. Imagination encircles the world."; Author = "Albert Einstein" }
        @{ Text = "Life is like riding a bicycle. To keep your balance, you must keep moving."; Author = "Albert Einstein" }
        @{ Text = "Strive not to be a success, but rather to be of value."; Author = "Albert Einstein" }
        @{ Text = "The important thing is not to stop questioning. Curiosity has its own reason for existing."; Author = "Albert Einstein" }
        @{ Text = "A person who never made a mistake never tried anything new."; Author = "Albert Einstein" }

        # Osho
        @{ Text = "Experience life in all possible ways - good-bad, bitter-sweet, dark-light, summer-winter. Experience all the dualities."; Author = "Osho" }
        @{ Text = "Creativity is the greatest rebellion in existence."; Author = "Osho" }
        @{ Text = "Be realistic: plan for a miracle."; Author = "Osho" }
        @{ Text = "If you are a parent, open doors to unknown directions to the child so he can explore. Don't make him afraid of the unknown."; Author = "Osho" }
        @{ Text = "The moment you accept yourself, you become beautiful."; Author = "Osho" }

        # Rumi
        @{ Text = "Yesterday I was clever, so I wanted to change the world. Today I am wise, so I am changing myself."; Author = "Rumi" }
        @{ Text = "The wound is the place where the light enters you."; Author = "Rumi" }
        @{ Text = "What you seek is seeking you."; Author = "Rumi" }
        @{ Text = "Silence is the language of God, all else is poor translation."; Author = "Rumi" }

        # Feynman
        @{ Text = "The first principle is that you must not fool yourself - and you are the easiest person to fool."; Author = "Richard Feynman" }
        @{ Text = "I would rather have questions that can't be answered than answers that can't be questioned."; Author = "Richard Feynman" }
        @{ Text = "Nobody ever figures out what life is all about, and it doesn't matter. Explore the world."; Author = "Richard Feynman" }

        # Nikola Tesla
        @{ Text = "The present is theirs; the future, for which I really worked, is mine."; Author = "Nikola Tesla" }
        @{ Text = "I don't care that they stole my idea. I care that they don't have any of their own."; Author = "Nikola Tesla" }

        # Marcus Aurelius / Stoics
        @{ Text = "You have power over your mind - not outside events. Realize this, and you will find strength."; Author = "Marcus Aurelius" }
        @{ Text = "The happiness of your life depends upon the quality of your thoughts."; Author = "Marcus Aurelius" }
        @{ Text = "Waste no more time arguing about what a good man should be. Be one."; Author = "Marcus Aurelius" }
        @{ Text = "It is not that we have a short time to live, but that we waste a great deal of it."; Author = "Seneca" }

        # Alan Watts
        @{ Text = "The only way to make sense out of change is to plunge into it, move with it, and join the dance."; Author = "Alan Watts" }
        @{ Text = "Muddy water is best cleared by leaving it alone."; Author = "Alan Watts" }
        @{ Text = "This is the real secret of life - to be completely engaged with what you are doing in the here and now."; Author = "Alan Watts" }

        # Lao Tzu
        @{ Text = "A journey of a thousand miles begins with a single step."; Author = "Lao Tzu" }
        @{ Text = "When I let go of what I am, I become what I might be."; Author = "Lao Tzu" }
        @{ Text = "Nature does not hurry, yet everything is accomplished."; Author = "Lao Tzu" }

        # Carl Sagan
        @{ Text = "Somewhere, something incredible is waiting to be known."; Author = "Carl Sagan" }
        @{ Text = "We are a way for the cosmos to know itself."; Author = "Carl Sagan" }

        # Nietzsche
        @{ Text = "He who has a why to live can bear almost any how."; Author = "Friedrich Nietzsche" }
        @{ Text = "One must still have chaos in oneself to be able to give birth to a dancing star."; Author = "Friedrich Nietzsche" }
        @{ Text = "And those who were seen dancing were thought to be insane by those who could not hear the music."; Author = "Friedrich Nietzsche" }

        # Others - deep / fun mix
        @{ Text = "We suffer more often in imagination than in reality."; Author = "Seneca" }
        @{ Text = "The unexamined life is not worth living."; Author = "Socrates" }
        @{ Text = "Knowing yourself is the beginning of all wisdom."; Author = "Aristotle" }
        @{ Text = "No man is free who is not master of himself."; Author = "Epictetus" }
        @{ Text = "Everything we hear is an opinion, not a fact. Everything we see is a perspective, not the truth."; Author = "Marcus Aurelius" }
        @{ Text = "In the middle of difficulty lies opportunity."; Author = "Albert Einstein" }
        @{ Text = "The mind is everything. What you think you become."; Author = "Buddha" }
        @{ Text = "Do not dwell in the past, do not dream of the future, concentrate the mind on the present moment."; Author = "Buddha" }
        @{ Text = "It does not matter how slowly you go as long as you do not stop."; Author = "Confucius" }
        @{ Text = "The best revenge is massive success."; Author = "Frank Sinatra" }
        @{ Text = "Stay hungry, stay foolish."; Author = "Steve Jobs" }
        @{ Text = "Logic will get you from A to B. Imagination will take you everywhere."; Author = "Albert Einstein" }
        @{ Text = "Turn your wounds into wisdom."; Author = "Oprah Winfrey" }
        @{ Text = "The cosmos is within us. We are made of star-stuff."; Author = "Carl Sagan" }
        @{ Text = "I have not failed. I've just found 10,000 ways that won't work."; Author = "Thomas Edison" }
    )
    return (Get-Random -InputObject $quotes)
}

function Get-GentleRoast {
    $roasts = @(
        "Your streak called... it's filing for divorce."
        "Yesterday's you would be disappointed. Today's you can fix that."
        "Even your procrastination is procrastinating at this point."
        "Your todo list has been gathering dust. It's developing feelings."
        "The streak is gone but hey, rock bottom is a solid foundation."
        "Plot twist: the tasks don't complete themselves."
        "Your future self is side-eyeing you right now."
        "Streak broken! Time for a comeback arc though."
        "The only streak you're maintaining is days of doing nothing."
        "Your todos sent a missing person report for your motivation."
        "Legend says the last time you checked a todo, dinosaurs roamed."
        "Your streak went out for milk and never came back."
    )
    return (Get-Random -InputObject $roasts)
}

function Get-StreakMilestoneMessage {
    param([int]$Days)
    $milestones = @{
        7   = "One whole week! You're building a habit!"
        14  = "Two weeks strong! This is becoming second nature."
        21  = "21 days - they say it takes this long to form a habit!"
        30  = "A full month! You're officially unstoppable."
        50  = "50 days! Half a hundred of pure dedication."
        75  = "75 days! Three quarters of the way to 100!"
        100 = "TRIPLE DIGITS! 100 days of consistency!"
        150 = "150 days! You're in the elite tier now."
        200 = "200 days! Almost a year of greatness."
        365 = "ONE FULL YEAR! Absolute legend status achieved!"
    }
    if ($milestones.ContainsKey($Days)) {
        return $milestones[$Days]
    }
    return $null
}

function Get-StreakEmoji {
    param([int]$Days, [bool]$IsBroken = $false)
    if ($IsBroken) { return [char]::ConvertFromUtf32(0x1F494) } # broken heart
    $milestone = Get-StreakMilestoneMessage -Days $Days
    if ($milestone) { return [char]::ConvertFromUtf32(0x1F3C6) } # trophy
    return [char]::ConvertFromUtf32(0x1F525) # fire
}

function Get-EmptyStateMessage {
    $messages = @(
        "Nothing here yet - add your first todo!"
        "A clean slate! What will you accomplish today?"
        "No todos? Either you're done or you haven't started..."
        "Your todo list is feeling lonely. Add something!"
        "Zero todos. The possibilities are endless!"
    )
    return (Get-Random -InputObject $messages)
}
