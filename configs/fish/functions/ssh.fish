function ssh --wraps ssh --description 'SSH with portable terminal capabilities'
    set -lx TERM xterm-256color
    command ssh $argv
end
